import json
from odoo import api, fields, models

STATE_OPTIONS = [("pending", "Sin despacho"), ("partial", "Parcial"), ("done", "Despachada completa"), ("adjusted", "Con ajustes/devoluciones"), ("excess", "Saldo excedido"), ("review", "Revisar")]
SLA_OPTIONS = [("no_rule", "Sin plazo"), ("invalid", "Datos por revisar"), ("adjusted", "Con ajustes"), ("on_time", "Despachada a tiempo"), ("late", "Despachada tarde"), ("overdue", "Pendiente vencida"), ("due_today", "Vence al corte"), ("open", "Pendiente en plazo")]


class DispatchInvoice(models.Model):
    _name = "dispatch.invoice"
    _description = "Factura para análisis de despachos"
    _order = "invoice_date desc, internal_number desc"
    _check_company_auto = True

    name = fields.Char(required=True, index=True)
    invoice_key = fields.Char(required=True, index=True)
    snapshot_id = fields.Many2one("dispatch.snapshot", required=True, ondelete="cascade", check_company=True, index=True)
    source_id = fields.Many2one(related="snapshot_id.source_id", store=True, index=True)
    company_id = fields.Many2one(related="snapshot_id.company_id", store=True, index=True)
    snapshot_state = fields.Selection(related="snapshot_id.state", store=True, index=True)
    cutoff_date = fields.Date(related="snapshot_id.cutoff_date", store=True)
    external_number = fields.Char(string="Factura (archivo)", index=True)
    invoice_type = fields.Char(string="Tipo")
    internal_number = fields.Char(string="NumeroFactura (archivo)", index=True)
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
    pending_tons = fields.Float(string="Toneladas pendientes", compute="_compute_pending_tons", store=True, digits=(16, 3))
    pending_boxes = fields.Float(string="Cajas pendientes", digits=(16, 3))
    pending_pallets = fields.Float(string="Pallets pendientes", digits=(16, 3))
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
    product_code = fields.Char(string="Código de producto", index=True)
    product = fields.Char(string="Producto")
    warehouse_code = fields.Char(string="Código de bodega")
    warehouse = fields.Char(string="Bodega")
    invoiced_qty = fields.Float(string="Facturado", digits=(16, 6))
    physical_qty = fields.Float(string="Despacho físico", digits=(16, 6))
    adjustment_qty = fields.Float(string="Ajuste/devolución", digits=(16, 6))
    reported_dispatched_qty = fields.Float(string="Despachado (origen)", digits=(16, 6))
    pending_qty = fields.Float(string="Pendiente", digits=(16, 6))
    last_dispatch_date = fields.Date(string="Último despacho")
    pending_weight = fields.Float(string="Peso pendiente (kg)")
    pending_boxes = fields.Float(string="Cajas pendientes")
    pending_pallets = fields.Float(string="Pallets pendientes")
    source_state = fields.Char(string="Estado en origen")
    address = fields.Char(string="Dirección original")
    comment = fields.Text(string="Comentario original")
    blocks = fields.Char(string="Bloques")
    locations = fields.Char(string="Ubicaciones")
    raw_data = fields.Json(string="Registro de origen")
