"""Pull an ERP snapshot on demand or every two hours; publish with the existing queue."""
from datetime import datetime
import logging

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from ..services.api_import import (ENDPOINT, DispatchAPIError, convert_dispatch_payload,
                                   fetch_dispatch_api, iter_api_chunks)

_logger = logging.getLogger(__name__)


class DispatchSourceAPI(models.Model):
    _inherit = "dispatch.source"

    api_sync_enabled = fields.Boolean(string="Sincronizar API cada 2 horas", default=False,
        help="Consulta getdatosdespachos en API Administrator. Active una sola fuente para este universo por empresa.")
    api_last_attempt_at = fields.Datetime(string="Último intento API", readonly=True, copy=False)
    api_last_success_at = fields.Datetime(string="Última respuesta válida", readonly=True, copy=False)
    api_last_auto_at = fields.Datetime(readonly=True, copy=False)
    api_last_result = fields.Selection([("queued", "Procesamiento solicitado"), ("unchanged", "Sin cambios"),
        ("busy", "Importación en curso"), ("error", "Error de consulta")], string="Resultado de consulta", readonly=True, copy=False)
    api_last_message = fields.Text(string="Detalle de sincronización", readonly=True, copy=False)
    api_last_snapshot_id = fields.Many2one("dispatch.snapshot", string="Última importación API", readonly=True,
        copy=False, check_company=True, ondelete="set null")
    api_snapshot_state = fields.Selection(related="api_last_snapshot_id.state", string="Estado de importación", readonly=True)

    @api.constrains("api_sync_enabled", "active", "company_id")
    def _check_api_source(self):
        for source in self.filtered(lambda r: r.api_sync_enabled and r.active):
            if self.search_count([("id", "!=", source.id), ("company_id", "=", source.company_id.id),
                                  ("api_sync_enabled", "=", True), ("active", "=", True)]):
                raise ValidationError(_("Active getdatosdespachos en una sola fuente por empresa para este universo."))

    def action_sync_api(self):
        """Operators may request the fixed feed, not change URL or credentials."""
        self.ensure_one()
        self._check_operator()  # Check source/company before scoped elevation.
        if not self.active:
            raise UserError(_("Active la fuente antes de sincronizarla."))
        worker = self.sudo().with_company(self.company_id)
        result = worker._sync_dispatch_api()
        if result.get("snapshot_id"):
            return worker.env["dispatch.snapshot"].browse(result["snapshot_id"]).action_open_progress()
        return {"type": "ir.actions.client", "tag": "display_notification", "params": {
            "title": _("Sincronización de despachos"), "message": result["message"],
            "type": "danger" if result.get("error") else "warning", "sticky": True}}

    def _sync_dispatch_api(self):
        self.ensure_one()
        # Same lock as Excel preparation/loading: never overlap a fetch and an
        # import for this source, even if cron and a user click at the same time.
        self.env.cr.execute("SELECT pg_try_advisory_xact_lock(%s, %s)", (180104, self.id))
        if not self.env.cr.fetchone()[0]:
            return {"message": _("La fuente está procesando otra solicitud. Consulte el avance y vuelva a intentar.")}
        self.invalidate_recordset()
        inflight = self.env["dispatch.snapshot"].search([
            ("source_id", "=", self.id), ("state", "in", ["receiving", "queued", "loading"])], order="id", limit=1)
        if inflight:
            self.write({"api_last_result": "busy", "api_last_message": _("Hay una importación en curso; no se inició otra descarga.")})
            return {"snapshot_id": inflight.id, "message": self.api_last_message}
        self.api_last_attempt_at = fields.Datetime.now()
        snapshot = None
        try:
            with self.env.cr.savepoint():
                # Cron and interactive sync agree on the exporter's local day.
                timezone = self.company_id.partner_id.tz or "America/Guayaquil"
                today = fields.Date.context_today(self.with_context(tz=timezone))
                dataset = convert_dispatch_payload(fetch_dispatch_api(self.env), today, timezone)
                current = self.active_snapshot_id
                if current and dataset["cutoff_date"] < str(current.cutoff_date):
                    raise DispatchAPIError(_("El corte de la API es anterior al vigente. Revise fecha_corte en el ERP; no se reemplazaron los datos actuales."))
                if (current and current.state == "ready" and current.input_type == "api"
                        and current.api_payload_checksum == dataset["checksum"]
                        and str(current.cutoff_date) == dataset["cutoff_date"]):
                    snapshot = current
                    result = "unchanged"
                    message = _("Sin cambios en la API para este corte. Se conserva la importación vigente, sin duplicar facturas.")
                else:
                    snapshot = self.env["dispatch.snapshot"].create({
                        "name": "%s · API · %s" % (self.name, dataset["cutoff_date"]),
                        "source_id": self.id, "company_id": self.company_id.id,
                        "cutoff_date": dataset["cutoff_date"], "input_type": "api", "state": "receiving",
                        "file_name": ENDPOINT, "api_payload_checksum": dataset["checksum"],
                    })
                    count = 0
                    for index, chunk in enumerate(iter_api_chunks(dataset["rows"])):
                        snapshot.api_append_chunk(index, chunk)
                        count += 1
                    snapshot.api_finalize(count, len(dataset["rows"]))
                    result = "queued"
                    message = _("Se recibieron %s líneas. El procesamiento por bloques actualiza las facturas por TipoFactura + NumeroFactura; el corte anterior sigue visible hasta terminar.") % len(dataset["rows"])
                self.write({"api_last_result": result, "api_last_message": message,
                            "api_last_success_at": fields.Datetime.now(), "api_last_snapshot_id": snapshot.id})
        except (DispatchAPIError, UserError, ValidationError) as exc:
            message = str(exc)
            self.write({"api_last_result": "error", "api_last_message": message})
            return {"error": True, "message": message}
        except Exception as exc:
            # Never expose or log response bodies, URLs or credential headers.
            _logger.error("Dispatch API sync failed: source=%s company=%s exception=%s", self.id, self.company_id.id, type(exc).__name__)
            message = _("No se pudo preparar la sincronización. El corte vigente se conserva. Revise la configuración y el registro del servidor.")
            self.write({"api_last_result": "error", "api_last_message": message})
            return {"error": True, "message": message}
        return {"snapshot_id": snapshot.id, "message": message, "unchanged": result == "unchanged"}

    @api.model
    def _cron_sync_dispatch_api(self):
        """One bounded HTTP fetch per cron batch; the scheduler continues others."""
        now = fields.Datetime.now()
        if isinstance(now, str):
            now = datetime.fromisoformat(now)
        cycle = now.replace(hour=now.hour - now.hour % 2, minute=0, second=0, microsecond=0)
        domain = [("api_sync_enabled", "=", True), ("active", "=", True),
                  "|", ("api_last_auto_at", "=", False), ("api_last_auto_at", "<", cycle)]
        source = self.sudo().search(domain, order="id", limit=1)
        processed = 0
        if source:
            source = source.with_company(source.company_id)
            # Use the source lock before marking this cycle. A second cron worker
            # must not start another HTTP fetch from an older ORM cache.
            self.env.cr.execute("SELECT pg_try_advisory_xact_lock(%s, %s)", (180104, source.id))
            if self.env.cr.fetchone()[0]:
                source.invalidate_recordset()
                if not source.api_last_auto_at or source.api_last_auto_at < cycle:
                    source.api_last_auto_at = now
                    source._sync_dispatch_api()
                    processed = 1
        remaining = self.sudo().search_count(domain)
        try:
            with self.env.cr.savepoint():
                self.env["ir.cron"]._notify_progress(done=processed, remaining=remaining)
        except Exception:
            _logger.warning("Could not notify dispatch API cron progress")


class DispatchSnapshotAPI(models.Model):
    _inherit = "dispatch.snapshot"

    api_payload_checksum = fields.Char(string="Huella de datos API", readonly=True, copy=False, index=True)
