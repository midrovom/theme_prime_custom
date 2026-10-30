import json
from odoo import api, fields, models, _
from odoo.exceptions import AccessError
from ..services.engine import aggregate_invoice, evaluate, invoice_key, latest_invoice_versions, normalize, unique_invoice_lines, weight_metrics, pallet_metrics

STATE_OPTIONS = [("pending", "Sin despacho"), ("partial", "Parcial"), ("done", "Despachada completa"), ("adjusted", "Con ajustes/devoluciones"), ("excess", "Saldo excedido"), ("review", "Revisar")]
SLA_OPTIONS = [("no_rule", "Sin plazo"), ("invalid", "Datos por revisar"), ("adjusted", "Con ajustes"), ("on_time", "Despachada a tiempo"), ("late", "Despachada tarde"), ("overdue", "Pendiente vencida"), ("due_today", "Vence al corte"), ("open", "Pendiente en plazo")]


class DispatchInvoice(models.Model):
    _name = "dispatch.invoice"
    _description = "Factura para análisis de despachos"
    _order = "invoice_date desc, internal_number desc"
    _check_company_auto = True

    name = fields.Char(required=True, index=True)
    invoice_key = fields.Char(required=True, index=True)
    is_current = fields.Boolean(string="Registro vigente único", default=False, index=True, readonly=True)
    snapshot_id = fields.Many2one("dispatch.snapshot", required=True, ondelete="cascade", check_company=True, index=True)
    source_id = fields.Many2one(related="snapshot_id.source_id", store=True, index=True)
    company_id = fields.Many2one(related="snapshot_id.company_id", store=True, index=True)
    snapshot_state = fields.Selection(related="snapshot_id.state", store=True, index=True)
    cutoff_date = fields.Date(related="snapshot_id.cutoff_date", store=True)
    external_number = fields.Char(string="Factura (archivo)", index=True)
    invoice_type = fields.Char(string="Tipo", required=True)
    internal_number = fields.Char(string="NumeroFactura (archivo)", index=True, required=True)
    establishment = fields.Char(string="Establecimiento", index=True)
    invoice_date = fields.Date(string="Fecha de factura", index=True)
    invoice_time = fields.Char(string="Hora original")
    customer_code = fields.Char(string="Código de cliente")
    customer = fields.Char(string="Cliente", index=True)
    city = fields.Char(string="Ciudad", index=True)
    delivery = fields.Char(string="Condición de entrega", index=True)
    warehouse = fields.Char(string="Bodega de análisis", index=True)
    warehouses = fields.Char(string="Bodegas de la factura")
    seller = fields.Char(string="Vendedor", index=True)
    state = fields.Selection(STATE_OPTIONS, string="Estado físico", index=True)
    pending = fields.Boolean(string="Tiene pendiente", index=True)
    pending_lines = fields.Integer(string="Líneas pendientes")
    line_count = fields.Integer(string="Líneas")
    source_grain = fields.Selection([("warehouse", "Consolidado por bodega"), ("product", "Producto y bodega"), ("mixed", "Mixto: revisar")], string="Detalle del origen", index=True)
    pending_weight = fields.Float(string="Peso pendiente (kg)", digits=(16, 3))
    invoiced_weight = fields.Float(string="Peso facturado conocido (kg)", digits=(16, 3))
    dispatched_weight = fields.Float(string="Peso despachado (kg)", digits=(16, 3))
    invoiced_weight_missing_rows = fields.Integer(string="Registros sin peso facturado medible")
    dispatched_weight_missing_rows = fields.Integer(string="Registros sin peso despachado medible")
    invoiced_tons = fields.Float(string="Toneladas facturadas conocidas", compute="_compute_weight_tons", store=True, digits=(16, 3))
    dispatched_tons = fields.Float(string="Toneladas despachadas", compute="_compute_weight_tons", store=True, digits=(16, 3))
    warehouse_ids = fields.Many2many("dispatch.warehouse", "dispatch_invoice_warehouse_rel", "invoice_id", "warehouse_id",
        string="Bodegas", compute="_compute_warehouses", store=True)
    pending_tons = fields.Float(string="Toneladas pendientes", compute="_compute_pending_tons", store=True, digits=(16, 3))
    pending_boxes = fields.Float(string="Cajas pendientes", digits=(16, 3))
    pending_pallets = fields.Float(string="Pallets pendientes", digits=(16, 3))
    invoiced_pallets = fields.Float(string="Pallets facturados conocidos", digits=(16, 3))
    invoiced_pallets_missing_rows = fields.Integer(string="Registros sin pallets facturados")
    pending_pallets_missing_rows = fields.Integer(string="Registros sin pallets pendientes")
    has_adjustment = fields.Boolean(string="Con ajustes/devoluciones", index=True)
    physically_completed = fields.Boolean(string="Despacho físico completo según origen", index=True)
    completion_date = fields.Date(string="Fecha del despacho completo")
    last_dispatch_date = fields.Date(string="Último despacho registrado")
    quality_flags = fields.Json(string="Observaciones de calidad")
    source_warnings = fields.Json(string="Errores de Excel en campos descriptivos")
    quality_details = fields.Text(string="Observaciones de la fuente", compute="_compute_audit_details")
    rule_details = fields.Text(string="Regla aplicada", compute="_compute_audit_details")
    quality_issue = fields.Boolean(string="Datos por revisar", index=True)
    age_days = fields.Integer(string="Antigüedad al corte (días)")
    lead_days = fields.Float(string="Tiempo total (días calendario)", aggregator="avg")
    lead_available = fields.Boolean(string="Tiempo medible", index=True)
    sla_elapsed_days = fields.Float(string="Tiempo según calendario SLA", aggregator="avg")
    sla_days = fields.Integer(string="Plazo aplicado (días)")
    sla_day_type = fields.Selection([("calendar", "Calendario"), ("business", "Hábiles")], string="Tipo de días")
    sla_rule_id = fields.Many2one("dispatch.sla", string="Regla aplicada", ondelete="set null", check_company=True)
    sla_configured = fields.Boolean(string="Plazo configurado", index=True)
    rule_snapshot = fields.Json(string="Parámetro aplicado (histórico)")
    deadline = fields.Date(string="Fecha máxima de despacho", index=True)
    sla_status = fields.Selection(SLA_OPTIONS, string="Cumplimiento", index=True)
    late_days = fields.Integer(string="Días de atraso")
    eligible = fields.Boolean(string="Evaluable", index=True)
    mature = fields.Boolean(string="Exigible", index=True)
    on_time = fields.Boolean(string="Despachada a tiempo", index=True)
    line_ids = fields.One2many("dispatch.invoice.line", "invoice_id", string="Registros de origen")
    _sql_constraints = [("snapshot_invoice", "unique(snapshot_id,invoice_key)", "La factura ya existe en este corte.")]

    @api.depends("pending_weight")
    def _compute_pending_tons(self):
        for invoice in self:
            invoice.pending_tons = invoice.pending_weight / 1000

    @api.depends("invoiced_weight", "dispatched_weight")
    def _compute_weight_tons(self):
        for invoice in self:
            invoice.invoiced_tons = invoice.invoiced_weight / 1000
            invoice.dispatched_tons = invoice.dispatched_weight / 1000

    @api.depends("line_ids.warehouse_id")
    def _compute_warehouses(self):
        for invoice in self:
            invoice.warehouse_ids = invoice.line_ids.mapped("warehouse_id")

    def init(self):
        self.env.cr.execute("""CREATE UNIQUE INDEX IF NOT EXISTS dispatch_invoice_current_unique
            ON dispatch_invoice(company_id, invoice_type, internal_number) WHERE is_current""")

    @api.model
    def _refresh_current_records(self, company_id):
        self.env.cr.execute("SELECT pg_advisory_xact_lock(%s, %s)", (180107, company_id))
        self.flush_model(["is_current", "invoice_key", "invoice_type", "internal_number", "company_id", "snapshot_id"])
        self.env["dispatch.snapshot"].flush_model(["state", "cutoff_date", "source_id"])
        self.env["dispatch.source"].flush_model(["active_snapshot_id"])
        self.env.cr.execute("""SELECT i.id,i.invoice_type,i.internal_number,s.cutoff_date,s.id FROM dispatch_invoice i
            JOIN dispatch_snapshot s ON s.id=i.snapshot_id
            JOIN dispatch_source src ON src.id=s.source_id AND src.active_snapshot_id=s.id
            WHERE i.company_id=%s AND s.state='ready'""", (company_id,))
        winner_ids = latest_invoice_versions([{"id":row[0],"invoice_type":row[1],"internal_number":row[2],
            "cutoff_date":row[3],"snapshot_id":row[4],"company_id":company_id} for row in self.env.cr.fetchall()])
        self.env.cr.execute("UPDATE dispatch_invoice SET is_current=false WHERE company_id=%s AND is_current", (company_id,))
        if winner_ids:
            self.env.cr.execute("UPDATE dispatch_invoice SET is_current=true WHERE id=ANY(%s)", (winner_ids,))
        self.invalidate_model(["is_current"])

    @api.model
    def _upsert_snapshot_values(self, snapshot, values):
        existing = self.search([("snapshot_id", "=", snapshot.id), ("invoice_key", "in", [v["invoice_key"] for v in values])])
        by_key = {r.invoice_key:r for r in existing}
        fresh = []
        for vals in values:
            record = by_key.get(vals["invoice_key"])
            if record:
                record.write({**vals, "line_ids": [(5, 0, 0), *vals["line_ids"]]})
            else:
                fresh.append(vals)
        if fresh: self.create(fresh)

    @api.model
    def _initialize_unique_records(self, companies=None):
        """Upgrade existing imports without uploading them again.

        Historical snapshots are versions, never an additive operational
        universe. Only redundant details within a snapshot are consolidated.
        """
        records = self.sudo()
        records.flush_model()
        self.env["dispatch.invoice.line"].flush_model()
        companies = companies if companies is not None else self.env["res.company"].sudo().search([])
        removed = 0
        for company in companies:
            self.env.cr.execute("SELECT pg_advisory_xact_lock(%s,%s)", (180107,company.id))
            self.env.cr.execute("UPDATE dispatch_invoice SET is_current=false WHERE company_id=%s", (company.id,))
            self.env.cr.execute("""SELECT array_agg(id ORDER BY id) FROM dispatch_invoice
                WHERE company_id=%s GROUP BY snapshot_id, upper(trim(invoice_type)), trim(internal_number)
                HAVING count(*)>1""", (company.id,))
            groups = self.env.cr.fetchall()
            for (ids,) in groups:
                invoices = records.browse(ids)
                keeper = invoices[-1]
                raw = [line.raw_data for invoice in invoices for line in invoice.line_ids if line.raw_data]
                unique, _, _ = unique_invoice_lines(raw)
                if not unique:
                    raise ValueError("No se puede consolidar %s sin sus registros de origen." % keeper.name)
                summary = aggregate_invoice(invoice_key(unique[0]), unique, keeper.cutoff_date)
                warehouse_map = self.env["dispatch.warehouse"]._ensure_records(company, unique)
                values = keeper.snapshot_id._invoice_values({"summary":summary,"lines":unique}, warehouse_map)
                invoices[:-1].unlink()
                keeper.write({**values,"line_ids":[(5,0,0),*values["line_ids"]]})
                removed += len(ids)-1
            self.env.cr.execute("""SELECT invoice_id FROM dispatch_invoice_line WHERE company_id=%s
                GROUP BY invoice_id,upper(trim(coalesce(warehouse_code,''))),coalesce(product_code,'')
                HAVING count(*)>1""",(company.id,))
            for identity in {row[0] for row in self.env.cr.fetchall()}:
                record=records.browse(identity)
                raw=[line.raw_data for line in record.line_ids if line.raw_data]
                unique,duplicates,_=unique_invoice_lines(raw)
                if duplicates:
                    summary=aggregate_invoice(invoice_key(unique[0]),unique,record.cutoff_date)
                    mapping=self.env["dispatch.warehouse"]._ensure_records(company,unique)
                    vals=record.snapshot_id._invoice_values({"summary":summary,"lines":unique},mapping)
                    record.write({**vals,"line_ids":[(5,0,0),*vals["line_ids"]]})
                    removed+=duplicates
            records.flush_model()
            self.env["dispatch.invoice.line"].flush_model()
            self.env.cr.execute("""UPDATE dispatch_invoice SET invoice_type=upper(trim(invoice_type)),
                internal_number=trim(internal_number),
                invoice_key='['||to_json(upper(trim(invoice_type)))::text||','||to_json(trim(internal_number))::text||']'
                WHERE company_id=%s""", (company.id,))
            lines = self.env["dispatch.invoice.line"].sudo()
            last_id = 0
            while True:
                batch = lines.search_read([("company_id","=",company.id),("id",">",last_id)],
                    ["raw_data","warehouse_code","warehouse","pending_qty","pending_weight"],order="id",limit=2000)
                if not batch: break
                warehouse_map = self.env["dispatch.warehouse"]._ensure_records(company,
                    [{"CodBodega":line["warehouse_code"],"Bodega":line["warehouse"]} for line in batch])
                values = []
                for line in batch:
                    raw = line["raw_data"] or {}
                    metrics = weight_metrics(raw)
                    pallets = pallet_metrics(raw)
                    warehouse_id = warehouse_map.get(normalize(line["warehouse_code"] or line["warehouse"]))
                    values.append((line["id"],warehouse_id,metrics["dispatched_weight"],metrics["invoiced_weight"],
                        metrics["dispatched_weight_available"],metrics["invoiced_weight_available"],
                        max(0,line["pending_weight"])/1000 if line["pending_qty"]>0.000001 else 0,
                        metrics["dispatched_weight"]/1000,metrics["invoiced_weight"]/1000,
                        pallets["invoiced_pallets"],pallets["invoiced_pallets_available"],
                        pallets["pending_pallets"],pallets["pending_pallets_available"]))
                placeholders = ",".join(["(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)"]*len(values))
                self.env.cr.execute("""UPDATE dispatch_invoice_line l SET warehouse_id=v.warehouse_id::int,
                    dispatched_weight=v.dispatched_weight::float8,invoiced_weight=v.invoiced_weight::float8,
                    dispatched_weight_available=v.dispatched_available::boolean,invoiced_weight_available=v.invoiced_available::boolean,
                    pending_tons=v.pending_tons::float8,dispatched_tons=v.dispatched_tons::float8,invoiced_tons=v.invoiced_tons::float8,
                    invoiced_pallets=v.invoiced_pallets::float8,invoiced_pallets_available=v.invoiced_pallets_available::boolean,
                    pending_pallets=v.pending_pallets::float8,pending_pallets_available=v.pending_pallets_available::boolean
                    FROM (VALUES """+placeholders+""") AS v(id,warehouse_id,dispatched_weight,invoiced_weight,
                    dispatched_available,invoiced_available,pending_tons,dispatched_tons,invoiced_tons,
                    invoiced_pallets,invoiced_pallets_available,pending_pallets,pending_pallets_available) WHERE l.id=v.id::int""",
                    [value for row in values for value in row])
                last_id=batch[-1]["id"]
            self.env.cr.execute("""UPDATE dispatch_invoice i SET
                invoiced_weight=w.invoiced_weight,dispatched_weight=w.dispatched_weight,
                invoiced_tons=w.invoiced_weight/1000,dispatched_tons=w.dispatched_weight/1000,
                invoiced_weight_missing_rows=w.invoiced_missing,dispatched_weight_missing_rows=w.dispatched_missing,
                invoiced_pallets=w.invoiced_pallets,pending_pallets=w.pending_pallets,
                invoiced_pallets_missing_rows=w.invoiced_pallets_missing,pending_pallets_missing_rows=w.pending_pallets_missing
                FROM (SELECT l.invoice_id,sum(l.invoiced_weight) invoiced_weight,sum(l.dispatched_weight) dispatched_weight,
                    count(*) FILTER (WHERE NOT l.invoiced_weight_available) invoiced_missing,
                    count(*) FILTER (WHERE NOT l.dispatched_weight_available) dispatched_missing,
                    sum(l.invoiced_pallets) invoiced_pallets,sum(l.pending_pallets) pending_pallets,
                    count(*) FILTER (WHERE NOT l.invoiced_pallets_available) invoiced_pallets_missing,
                    count(*) FILTER (WHERE NOT l.pending_pallets_available) pending_pallets_missing
                    FROM dispatch_invoice_line l WHERE l.company_id=%s GROUP BY l.invoice_id) w WHERE i.id=w.invoice_id""", (company.id,))
            self.env.cr.execute("""INSERT INTO dispatch_invoice_warehouse_rel(invoice_id,warehouse_id)
                SELECT DISTINCT invoice_id,warehouse_id FROM dispatch_invoice_line WHERE company_id=%s AND warehouse_id IS NOT NULL
                ON CONFLICT DO NOTHING""", (company.id,))
            self.env.cr.execute("""UPDATE dispatch_snapshot s SET total_invoices=x.count,loaded_invoices=x.count
                FROM (SELECT snapshot_id,count(*) count FROM dispatch_invoice WHERE company_id=%s GROUP BY snapshot_id) x
                WHERE s.id=x.snapshot_id AND s.state IN ('ready','archived')""",(company.id,))
            lines.invalidate_model()
            records.invalidate_model()
            records._refresh_current_records(company.id)
        return removed

    @api.depends("quality_flags", "source_warnings", "rule_snapshot")
    def _compute_audit_details(self):
        for invoice in self:
            notes = [flag.replace("_", " ").capitalize() for flag in invoice.quality_flags or []]
            notes += ["Excel %s (%s): %s" % (warning["cell"], warning["column"], warning["error"]) for warning in invoice.source_warnings or []]
            invoice.quality_details = "\n".join(notes) or "Sin observaciones"
            invoice.rule_details = json.dumps(invoice.rule_snapshot or {}, ensure_ascii=False, indent=2)


class DispatchInvoiceLine(models.Model):
    _name = "dispatch.invoice.line"
    _description = "Línea original del análisis de despachos"
    _check_company_auto = True
    _rec_name = "product"

    invoice_id = fields.Many2one("dispatch.invoice", required=True, ondelete="cascade", check_company=True, index=True)
    company_id = fields.Many2one(related="invoice_id.company_id", store=True, index=True)
    invoice_date = fields.Date(related="invoice_id.invoice_date", store=True, string="Fecha de factura", index=True)
    city = fields.Char(related="invoice_id.city", store=True, string="Destino", index=True)
    delivery = fields.Char(related="invoice_id.delivery", store=True, string="Modalidad", index=True)
    snapshot_id = fields.Many2one(related="invoice_id.snapshot_id", store=True, string="Importación", index=True)
    product_code = fields.Char(string="Código de producto", index=True)
    product = fields.Char(string="Producto")
    warehouse_code = fields.Char(string="Código de bodega")
    warehouse = fields.Char(string="Bodega")
    warehouse_id = fields.Many2one("dispatch.warehouse", string="Bodega de origen", check_company=True, index=True)
    invoiced_qty = fields.Float(string="Facturado", digits=(16, 6))
    physical_qty = fields.Float(string="Despacho físico", digits=(16, 6))
    adjustment_qty = fields.Float(string="Ajuste/devolución", digits=(16, 6))
    reported_dispatched_qty = fields.Float(string="Despachado (origen)", digits=(16, 6))
    pending_qty = fields.Float(string="Pendiente", digits=(16, 6))
    last_dispatch_date = fields.Date(string="Último despacho")
    pending_weight = fields.Float(string="Peso pendiente (kg)")
    dispatched_weight = fields.Float(string="Peso despachado (kg)")
    invoiced_weight = fields.Float(string="Peso facturado conocido (kg)")
    dispatched_weight_available = fields.Boolean(string="Peso despachado disponible")
    invoiced_weight_available = fields.Boolean(string="Peso facturado disponible")
    pending_tons = fields.Float(string="Toneladas pendientes", compute="_compute_tons", store=True, digits=(16, 3))
    dispatched_tons = fields.Float(string="Toneladas despachadas", compute="_compute_tons", store=True, digits=(16, 3))
    invoiced_tons = fields.Float(string="Toneladas facturadas conocidas", compute="_compute_tons", store=True, digits=(16, 3))
    pending_boxes = fields.Float(string="Cajas pendientes")
    pending_pallets = fields.Float(string="Pallets pendientes")
    invoiced_pallets = fields.Float(string="Pallets facturados conocidos")
    invoiced_pallets_available = fields.Boolean(string="Pallets facturados disponibles")
    pending_pallets_available = fields.Boolean(string="Pallets pendientes disponibles")
    source_state = fields.Char(string="Estado en origen")
    address = fields.Char(string="Dirección original")
    comment = fields.Text(string="Comentario original")
    blocks = fields.Char(string="Bloques")
    locations = fields.Char(string="Ubicaciones")
    raw_data = fields.Json(string="Registro de origen")

    @api.depends("pending_qty", "pending_weight", "dispatched_weight", "invoiced_weight")
    def _compute_tons(self):
        for line in self:
            line.pending_tons = max(0, line.pending_weight) / 1000 if line.pending_qty > 0.000001 else 0
            line.dispatched_tons = line.dispatched_weight / 1000
            line.invoiced_tons = line.invoiced_weight / 1000
