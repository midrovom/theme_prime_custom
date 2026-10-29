import base64
import hashlib
import json
import logging
import uuid
from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError
from ..services.engine import aggregate_invoice, as_date, evaluate, iter_invoice_groups, normalize, number
from ..services.xlsx_reader import iter_xlsx_rows
from ..services.import_progress import ACTIVE_STATES, progress_values

_logger = logging.getLogger(__name__)
BATCH_SIZE = 500
STATES = [("receiving", "Recibiendo API"), ("queued", "En cola"), ("loading", "Importando"),
          ("ready", "Corte vigente"), ("archived", "Histórico"), ("error", "Error")]


class DispatchSnapshot(models.Model):
    _name = "dispatch.snapshot"
    _description = "Corte de datos de despachos"
    _order = "cutoff_date desc,id desc"
    _check_company_auto = True

    name = fields.Char(required=True)
    source_id = fields.Many2one("dispatch.source", required=True, ondelete="restrict", check_company=True, index=True)
    company_id = fields.Many2one("res.company", required=True, default=lambda s: s.env.company, index=True)
    batch_key = fields.Char(required=True, index=True, default=lambda s: str(uuid.uuid4()))
    cutoff_date = fields.Date(required=True, string="Corte de datos")
    input_type = fields.Selection([("xlsx", "Excel"), ("api", "API")], required=True)
    state = fields.Selection(STATES, required=True, default="queued", index=True)
    file_name = fields.Char()
    raw_file = fields.Binary(attachment=True, string="Excel original", copy=False)
    policy_pack = fields.Json(string="Plazos y feriados aplicados", copy=False)
    policy_description = fields.Text(string="Parámetros del corte", compute="_compute_policy_description")
    total_rows = fields.Integer(string="Líneas recibidas", readonly=True)
    total_invoices = fields.Integer(string="Facturas detectadas", readonly=True)
    loaded_invoices = fields.Integer(string="Facturas importadas", readonly=True)
    started_at = fields.Datetime(readonly=True)
    finished_at = fields.Datetime(readonly=True)
    last_progress_at = fields.Datetime(string="Último avance", readonly=True)
    progress_percent = fields.Float(string="Progreso de facturas", compute="_compute_progress", digits=(16, 1))
    progress_message = fields.Char(string="Avance", compute="_compute_progress")
    error_message = fields.Text(string="Detalle del error", readonly=True)
    chunk_ids = fields.One2many("dispatch.chunk", "snapshot_id")
    invoice_ids = fields.One2many("dispatch.invoice", "snapshot_id")
    _sql_constraints = [("source_batch_key", "unique(source_id,batch_key)", "El identificador del lote ya existe en esta fuente.")]

    @api.depends("state", "total_invoices", "loaded_invoices", "total_rows")
    def _compute_progress(self):
        for snapshot in self:
            values = progress_values(snapshot.state, snapshot.loaded_invoices, snapshot.total_invoices, snapshot.total_rows)
            snapshot.progress_percent = values["progress_percent"]
            snapshot.progress_message = values["progress_message"]

    def action_open_progress(self):
        self.ensure_one()
        self.check_access_rights("read")
        self.check_access_rule("read")
        return {"type": "ir.actions.client", "name": _("Importación de despachos"),
                "tag": "transcash_dispatch_import_progress", "params": {"snapshot_id": self.id}}

    def get_import_progress(self):
        self.ensure_one()
        self.check_access_rights("read")
        self.check_access_rule("read")
        return self._progress_payload()

    def _progress_payload(self, busy=False):
        values = progress_values(self.state, self.loaded_invoices, self.total_invoices, self.total_rows)
        values.update({"id": self.id, "name": self.name, "state": self.state,
            "file_name": self.file_name or self.name, "total_rows": self.total_rows,
            "total_invoices": self.total_invoices, "loaded_invoices": self.loaded_invoices,
            "error_message": self.error_message or "", "busy": busy,
            "last_progress_at": str(self.last_progress_at) if self.last_progress_at else False,
            "can_process": self.env.su or self.env.user.has_group("transcash_dispatch_analysis.group_dispatch_operator")})
        return values

    def process_import_step(self):
        """One bounded RPC transaction; explicit access check BEFORE elevation.

        The operator can import an allowed source but has no general permission
        to create analytical invoices. Elevation is limited to this checked job.
        """
        self._operator()
        worker = self.sudo().with_context(bin_size=False)
        if not worker._try_import_lock():
            return self._progress_payload(busy=True)
        worker.invalidate_recordset()
        worker._run_import_step()
        return worker._progress_payload()

    def _try_import_lock(self):
        self.ensure_one()
        self.env.cr.execute("SELECT pg_try_advisory_xact_lock(%s, %s)", (180104, self.source_id.id))
        return bool(self.env.cr.fetchone()[0])

    def _run_import_step(self):
        self.ensure_one()
        if self.state not in ACTIVE_STATES:
            return False
        try:
            with self.env.cr.savepoint():
                if self.state == "queued":
                    self._prepare()
                else:
                    self._load_next()
                self.last_progress_at = fields.Datetime.now()
        except Exception as exc:
            _logger.exception("Dispatch import failed for snapshot %s", self.id)
            self.write({"state": "error", "error_message": str(exc)[:3000], "last_progress_at": fields.Datetime.now()})
        return True

    def _schedule_import(self):
        """Scheduling failure must not roll back an upload or a completed block."""
        cron = self.env.ref("transcash_dispatch_analysis.cron_dispatch_import", raise_if_not_found=False)
        if not cron:
            return
        try:
            with self.env.cr.savepoint():
                if cron.sudo().active:
                    cron.sudo()._trigger()
        except Exception:
            _logger.warning("Could not schedule dispatch import; the interactive runner remains available", exc_info=True)

    @api.depends("policy_pack")
    def _compute_policy_description(self):
        for snapshot in self:
            snapshot.policy_description = json.dumps(snapshot.policy_pack or {}, ensure_ascii=False, indent=2)

    @api.constrains("cutoff_date", "company_id", "source_id")
    def _check_dates(self):
        for snapshot in self:
            if snapshot.cutoff_date > fields.Date.context_today(snapshot):
                raise ValidationError(_("El corte de datos no puede ser posterior a hoy."))
            if snapshot.source_id.company_id != snapshot.company_id:
                raise ValidationError(_("La fuente pertenece a otra compañía."))

    def _operator(self):
        self.ensure_one()
        self.source_id._check_operator()
        self.check_access_rights("write")
        self.check_access_rule("write")

    def api_append_chunk(self, index, rows):
        """Idempotent upload. Same index + same checksum is safe to retry."""
        self._operator()
        if self.input_type != "api":
            raise ValidationError(_("El lote no es de API."))
        if isinstance(index, bool) or not isinstance(index, int) or index < 0:
            raise ValidationError(_("El índice debe ser un entero desde cero."))
        if not isinstance(rows, list) or not 1 <= len(rows) <= 5000 or any(not isinstance(r, dict) for r in rows):
            raise ValidationError(_("Envíe entre 1 y 5.000 objetos por bloque."))
        try:
            payload = json.dumps(rows, ensure_ascii=False, sort_keys=True, allow_nan=False, separators=(",", ":")).encode()
        except (ValueError, TypeError) as exc:
            raise ValidationError(_("El bloque contiene datos JSON inválidos.")) from exc
        if len(payload) > 20 * 1024 * 1024:
            raise ValidationError(_("El bloque supera 20 MiB."))
        checksum = hashlib.sha256(payload).hexdigest()
        existing = self.env["dispatch.chunk"].search([("snapshot_id", "=", self.id), ("phase", "=", "raw"), ("sequence", "=", index)], limit=1)
        if existing:
            if existing.checksum != checksum:
                raise ValidationError(_("El índice ya fue recibido con otro contenido."))
            return {"id": existing.id, "duplicate": True}
        if self.state != "receiving":
            raise ValidationError(_("El lote ya no está recibiendo bloques."))
        current = sum(self.chunk_ids.filtered(lambda c: c.phase == "raw").mapped("row_count"))
        if current + len(rows) > 500_000:
            raise ValidationError(_("El lote supera 500.000 líneas."))
        chunk = self.env["dispatch.chunk"].create({"snapshot_id": self.id, "phase": "raw", "sequence": index,
            "payload": base64.b64encode(payload), "checksum": checksum, "row_count": len(rows)})
        return {"id": chunk.id, "duplicate": False}

    def api_finalize(self, expected_chunks, expected_rows):
        self._operator()
        if any(isinstance(n, bool) or not isinstance(n, int) or n < 0 for n in (expected_chunks, expected_rows)):
            raise ValidationError(_("Los controles esperados deben ser enteros no negativos."))
        chunks = self.chunk_ids.filtered(lambda c: c.phase == "raw").sorted("sequence")
        if len(chunks) != expected_chunks or chunks.mapped("sequence") != list(range(expected_chunks)):
            raise ValidationError(_("Faltan bloques o la secuencia no comienza en cero."))
        if sum(chunks.mapped("row_count")) != expected_rows:
            raise ValidationError(_("El total de líneas no coincide con el control enviado."))
        if self.state == "receiving":
            # An empty FULL snapshot is allowed, but requires explicit zero controls.
            self.write({"state": "queued", "total_rows": expected_rows})
            self._schedule_import()
        elif self.state not in ("queued", "loading", "ready", "archived"):
            raise ValidationError(_("El lote requiere corregir el error antes de finalizar."))
        return {"id": self.id, "state": self.state, "rows": expected_rows}

    def action_retry(self):
        self._operator()
        if self.state != "error":
            raise UserError(_("Solo se puede reintentar un lote con error."))
        self.write({"state": "queued", "error_message": False})
        self._schedule_import()
        return self.action_open_progress()

    def action_recalculate(self):
        """Build a new immutable snapshot; do not alter existing historical KPIs."""
        self.ensure_one()
        if not self.env.su and not self.env.user.has_group("transcash_dispatch_analysis.group_dispatch_manager"):
            raise AccessError(_("Solo un responsable puede reaplicar parámetros."))
        self.check_access_rights("read")
        self.check_access_rule("read")
        if self.state not in ("ready", "archived"):
            raise UserError(_("Seleccione un corte terminado."))
        clone = self.create({"name": "%s · nuevos parámetros" % self.name, "source_id": self.source_id.id,
            "company_id": self.company_id.id, "cutoff_date": self.cutoff_date, "input_type": self.input_type,
            "raw_file": self.raw_file, "file_name": self.file_name, "state": "queued", "total_rows": self.total_rows})
        if self.input_type == "api":
            for chunk in self.chunk_ids.filtered(lambda c: c.phase == "raw"):
                chunk.copy({"snapshot_id": clone.id})
        clone._schedule_import()
        return clone.action_open_progress()

    def action_open_invoices(self):
        self.ensure_one()
        self.check_access_rights("read")
        self.check_access_rule("read")
        return {"type": "ir.actions.act_window", "name": self.name, "res_model": "dispatch.invoice", "view_mode": "list,form,pivot,graph", "domain": [("snapshot_id", "=", self.id)]}

    def _rows(self):
        if self.input_type == "xlsx":
            if not self.raw_file:
                raise ValueError("El corte no tiene el Excel original.")
            yield from iter_xlsx_rows(base64.b64decode(self.with_context(bin_size=False).raw_file))
        else:
            for chunk in self.with_context(bin_size=False).chunk_ids.filtered(lambda c: c.phase == "raw").sorted("sequence"):
                yield from json.loads(base64.b64decode(chunk.payload))

    def _prepare(self):
        self.ensure_one()
        # A failed attempt is disposable and never became the active source.
        self.invoice_ids.unlink()
        self.chunk_ids.filtered(lambda c: c.phase == "prepared").unlink()
        self.write({"started_at": fields.Datetime.now(), "loaded_invoices": 0, "error_message": False})
        batch, seq, row_count, invoice_count = [], 0, 0, 0
        cities = set()
        for key, rows in iter_invoice_groups(self._rows()):
            summary = aggregate_invoice(key, rows, self.cutoff_date)
            cities.update(normalize(row.get("Ciudad")) for row in rows)
            batch.append({"summary": summary, "lines": rows})
            row_count += len(rows)
            invoice_count += 1
            if len(batch) >= BATCH_SIZE:
                self._store_prepared(seq, batch)
                seq += 1
                batch = []
        if batch:
            self._store_prepared(seq, batch)
        if self.input_type == "api" and row_count != self.total_rows:
            raise ValueError("Las líneas leídas no coinciden con las líneas finalizadas por API.")
        if self.input_type == "xlsx" and not row_count:
            raise ValueError("El Excel no contiene registros. No se reemplazó el corte vigente.")
        # Capture the pack only after every detected city has its initial rule.
        # This is shared by Excel, API and parameter reapplication.
        self.env["dispatch.sla"]._ensure_city_defaults(self.company_id, cities)
        self.write({"state": "loading", "total_rows": row_count, "total_invoices": invoice_count,
                    "policy_pack": self.env["dispatch.sla"]._policy_pack(self.company_id)})
        if not invoice_count:
            self._activate()

    def _store_prepared(self, sequence, data):
        payload = json.dumps(data, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode()
        self.env["dispatch.chunk"].create({"snapshot_id": self.id, "phase": "prepared", "sequence": sequence,
            "payload": base64.b64encode(payload), "checksum": hashlib.sha256(payload).hexdigest(), "row_count": len(data)})

    def _invoice_values(self, item):
        calculated = evaluate(item["summary"], self.policy_pack or {})
        values = {k: v for k, v in calculated.items() if k in self.env["dispatch.invoice"]._fields and k != "cutoff_date"}
        values.update({"snapshot_id": self.id, "lead_available": calculated["lead_days"] is not None,
                       "lead_days": calculated["lead_days"] or 0.0, "sla_elapsed_days": calculated["sla_elapsed_days"] or 0.0})
        commands = []
        for row in item["lines"]:
            values_line = {
                "product_code": str(row.get("CodProducto") or ""), "product": str(row.get("Producto") or ("Resumen por bodega (sin SKU)" if not row.get("CodProducto") else "")),
                "warehouse_code": str(row.get("CodBodega") or ""), "warehouse": str(row.get("Bodega") or ""),
                "invoiced_qty": number(row.get("Facturado")), "physical_qty": number(row.get("DespachoFisico")),
                "adjustment_qty": number(row.get("AjusteDevolucion")), "reported_dispatched_qty": number(row.get("Despachado")),
                "pending_qty": number(row.get("Pendiente")), "last_dispatch_date": as_date(row.get("UltimoDespacho")),
                "pending_weight": number(row.get("PesoPendiente")), "pending_boxes": number(row.get("CajasPendientes")),
                "pending_pallets": number(row.get("PalletsPendientes")), "source_state": str(row.get("EstadoDespacho") or ""),
                "address": str(row.get("Direccion") or ""), "comment": str(row.get("Comentario") or ""),
                "blocks": str(row.get("Bloques") or ""), "locations": str(row.get("Ubicaciones") or ""), "raw_data": row,
            }
            commands.append(fields.Command.create(values_line))
        values["line_ids"] = commands
        return values

    def _load_next(self):
        chunk = self.env["dispatch.chunk"].search([("snapshot_id", "=", self.id), ("phase", "=", "prepared"), ("loaded", "=", False)], order="sequence", limit=1)
        if chunk:
            data = json.loads(base64.b64decode(chunk.with_context(bin_size=False).payload))
            if len(data) != chunk.row_count:
                raise ValueError("El bloque preparado no coincide con su control de facturas. Reintente la importación.")
            self.env["dispatch.invoice"].create([self._invoice_values(item) for item in data])
            self.loaded_invoices += len(data)
            chunk.loaded = True
        elif self.loaded_invoices != self.total_invoices:
            raise ValueError("Faltan bloques preparados: se importaron %s de %s facturas. Use Reintentar para reconstruir el corte desde el archivo guardado." % (self.loaded_invoices, self.total_invoices))
        if self.loaded_invoices > self.total_invoices:
            raise ValueError("El total importado supera el control de facturas del archivo.")
        if self.loaded_invoices == self.total_invoices:
            self._activate()

    def _activate(self):
        self.ensure_one()
        previous = self.source_id.active_snapshot_id
        # A delayed historical import must never replace fresher data.
        newer = previous and (previous.cutoff_date, previous.id) > (self.cutoff_date, self.id)
        self.write({"state": "archived" if newer else "ready", "finished_at": fields.Datetime.now()})
        if not newer:
            if previous and previous != self:
                previous.state = "archived"
            self.source_id.active_snapshot_id = self
        # Temporary transform blocks are reproducible from raw_file/raw chunks.
        self.chunk_ids.filtered(lambda c: c.phase == "prepared").unlink()

    @api.model
    def _cron_process(self):
        processed = 0
        for snapshot in self.search([("state", "in", list(ACTIVE_STATES))], order="id", limit=20):
            if not snapshot._try_import_lock():
                continue
            snapshot.invalidate_recordset()
            processed += int(snapshot._run_import_step())
            if processed:
                break
        remaining = self.search_count([("state", "in", list(ACTIVE_STATES))])
        # Notification is optional bookkeeping. A failure here used to escape
        # the import's savepoint and could undo a successful preparation/batch.
        try:
            with self.env.cr.savepoint():
                notify = getattr(self.env["ir.cron"], "_notify_progress", None)
                if notify:
                    notify(done=processed, remaining=remaining)
        except Exception:
            _logger.warning("Could not notify dispatch cron progress; imported data is preserved", exc_info=True)


class DispatchChunk(models.Model):
    _name = "dispatch.chunk"
    _description = "Bloque de importación de despachos"
    _order = "phase,sequence"
    _check_company_auto = True

    snapshot_id = fields.Many2one("dispatch.snapshot", required=True, ondelete="cascade", check_company=True, index=True)
    company_id = fields.Many2one(related="snapshot_id.company_id", store=True, index=True)
    phase = fields.Selection([("raw", "Recibido"), ("prepared", "Preparado")], required=True)
    sequence = fields.Integer(required=True)
    payload = fields.Binary(attachment=True, required=True, copy=True)
    checksum = fields.Char(required=True)
    row_count = fields.Integer()
    loaded = fields.Boolean(default=False)
    _sql_constraints = [("snapshot_phase_sequence", "unique(snapshot_id,phase,sequence)", "El bloque ya existe.")]
