from datetime import date
import uuid
from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError
from ..services.engine import normalize


class DispatchSource(models.Model):
    _name = "dispatch.source"
    _description = "Fuente de análisis de despachos"
    _check_company_auto = True

    name = fields.Char(required=True)
    code = fields.Char(required=True, index=True)
    company_id = fields.Many2one("res.company", required=True, default=lambda s: s.env.company, index=True)
    active = fields.Boolean(default=True)
    active_snapshot_id = fields.Many2one("dispatch.snapshot", readonly=True, check_company=True, ondelete="set null")
    notes = fields.Text()
    _sql_constraints = [("source_company_code", "unique(company_id,code)", "El código de fuente ya existe en esta compañía.")]

    def _check_operator(self):
        if not self.env.su and not self.env.user.has_group("transcash_dispatch_analysis.group_dispatch_operator"):
            raise AccessError(_("Necesita el permiso Operador de despachos."))
        self.check_access_rights("read")
        self.check_access_rule("read")
        if not self.env.su and any(s.company_id not in self.env.companies for s in self):
            raise AccessError(_("La compañía no está habilitada en su sesión."))

    def api_start_batch(self, batch_key, cutoff_date):
        """Public XML-RPC API: create/resume a COMPLETE source snapshot."""
        self.ensure_one()
        self._check_operator()
        if not isinstance(batch_key, str) or not batch_key.strip() or len(batch_key) > 160:
            raise ValidationError(_("batch_key debe tener entre 1 y 160 caracteres."))
        cutoff = fields.Date.to_date(cutoff_date)
        if not cutoff or cutoff > fields.Date.context_today(self):
            raise ValidationError(_("El corte debe ser una fecha válida hasta hoy."))
        found = self.env["dispatch.snapshot"].search([("source_id", "=", self.id), ("batch_key", "=", batch_key)], limit=1)
        if found:
            if found.cutoff_date != cutoff:
                raise ValidationError(_("El batch_key ya existe con otro corte."))
            return {"id": found.id, "state": found.state}
        snapshot = self.env["dispatch.snapshot"].create({
            "name": "%s · %s" % (self.name, cutoff), "source_id": self.id,
            "company_id": self.company_id.id, "batch_key": batch_key,
            "cutoff_date": cutoff, "input_type": "api", "state": "receiving",
        })
        return {"id": snapshot.id, "state": snapshot.state}


class DispatchSla(models.Model):
    _name = "dispatch.sla"
    _description = "Plazo de despacho por ciudad"
    _order = "city, delivery, valid_from"
    _check_company_auto = True

    name = fields.Char(compute="_compute_name", store=True)
    company_id = fields.Many2one("res.company", required=True, default=lambda s: s.env.company, index=True)
    active = fields.Boolean(default=True)
    city = fields.Char(help="Vacío: regla general para ciudades sin otra regla específica.")
    city_key = fields.Char(compute="_compute_keys", store=True, index=True)
    delivery = fields.Char(string="Condición de entrega", help="Vacío: todas. Escriba el texto de Cond_Entrega para una modalidad específica.")
    delivery_key = fields.Char(compute="_compute_keys", store=True)
    max_days = fields.Integer(string="Días máximos", required=True, default=2)
    day_type = fields.Selection([("calendar", "Calendario"), ("business", "Hábiles (lunes a viernes)")], default="calendar", required=True)
    valid_from = fields.Date(string="Facturas desde", required=True, default=lambda s: date(1900, 1, 1))
    valid_to = fields.Date(string="Facturas hasta")
    notes = fields.Text()

    @api.depends("city", "delivery")
    def _compute_keys(self):
        for rule in self:
            rule.city_key = normalize(rule.city)
            rule.delivery_key = normalize(rule.delivery)

    @api.depends("city", "delivery", "max_days", "day_type")
    def _compute_name(self):
        for rule in self:
            rule.name = "%s / %s · %s días %s" % (rule.city or "Todas las ciudades", rule.delivery or "Todas las modalidades", rule.max_days, "hábiles" if rule.day_type == "business" else "calendario")

    @api.constrains("max_days", "valid_from", "valid_to", "city_key", "delivery_key", "company_id", "active")
    def _check_rules(self):
        for rule in self:
            if rule.max_days < 0 or rule.max_days > 3650:
                raise ValidationError(_("El plazo debe estar entre 0 y 3.650 días."))
            if rule.valid_to and rule.valid_to < rule.valid_from:
                raise ValidationError(_("La fecha final debe ser igual o posterior a la inicial."))
            if not rule.active:
                continue
            others = self.search([("id", "!=", rule.id), ("company_id", "=", rule.company_id.id), ("city_key", "=", rule.city_key or False), ("delivery_key", "=", rule.delivery_key or False)])
            for other in others:
                if rule.valid_from <= (other.valid_to or date.max) and other.valid_from <= (rule.valid_to or date.max):
                    raise ValidationError(_("Existen plazos de igual prioridad con vigencias superpuestas."))

    @api.model
    def _policy_pack(self, company):
        rules = self.search([("company_id", "=", company.id)])
        holidays = self.env["dispatch.holiday"].search([("company_id", "=", company.id)])
        return {
            "rules": [{"id": r.id, "city_key": r.city_key or "", "delivery_key": r.delivery_key or "", "max_days": r.max_days,
                       "day_type": r.day_type, "valid_from": str(r.valid_from), "valid_to": str(r.valid_to) if r.valid_to else False} for r in rules],
            "holidays": [str(h.day) for h in holidays],
            "captured_at": str(fields.Datetime.now()),
        }


class DispatchHoliday(models.Model):
    _name = "dispatch.holiday"
    _description = "Feriado para los plazos de despacho"
    _order = "day"

    name = fields.Char(required=True)
    day = fields.Date(required=True, index=True)
    company_id = fields.Many2one("res.company", required=True, default=lambda s: s.env.company)
    _sql_constraints = [("holiday_company_day", "unique(company_id,day)", "El feriado ya está registrado.")]


METRIC_OPTIONS = [("total", "Facturas"), ("pending", "Facturas pendientes"), ("overdue", "Pendientes vencidas"),
                  ("mature_compliance", "Cumplimiento exigible (%)"), ("completed_compliance", "Cumplimiento despachadas (%)"),
                  ("lead_avg", "Tiempo promedio (días calendario)"), ("lead_median", "Mediana de despacho (días calendario)"), ("lead_p90", "P90 de despacho (días calendario)"), ("pending_weight", "Peso pendiente (kg)")]
DIMENSION_OPTIONS = [("city", "Ciudad"), ("delivery", "Condición de entrega"), ("warehouse", "Bodega"), ("seller", "Vendedor"), ("month", "Mes de factura")]


class DispatchBoard(models.Model):
    _name = "dispatch.board"
    _description = "Tablero personal de despachos"
    _check_company_auto = True

    name = fields.Char(required=True)
    company_id = fields.Many2one("res.company", required=True, default=lambda s: s.env.company)
    owner_id = fields.Many2one("res.users", required=True, default=lambda s: s.env.user)
    shared = fields.Boolean(string="Compartido con la compañía")
    widget_ids = fields.One2many("dispatch.widget", "board_id", string="Indicadores")

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.su and not self.env.user.has_group("transcash_dispatch_analysis.group_dispatch_manager"):
            for vals in vals_list:
                vals["owner_id"] = self.env.uid
                vals["shared"] = False
        return super().create(vals_list)

    def write(self, vals):
        if not self.env.su and not self.env.user.has_group("transcash_dispatch_analysis.group_dispatch_manager") and {"owner_id", "shared", "company_id"} & vals.keys():
            raise AccessError(_("Solo un responsable puede cambiar propietario, compañía o compartir un tablero."))
        return super().write(vals)

    def action_open(self):
        self.ensure_one()
        return {"type": "ir.actions.client", "tag": "transcash_dispatch_dashboard", "params": {"board_id": self.id}}


class DispatchWidget(models.Model):
    _name = "dispatch.widget"
    _description = "Visual configurable de despachos"
    _order = "sequence,id"
    _check_company_auto = True

    name = fields.Char(required=True)
    board_id = fields.Many2one("dispatch.board", required=True, ondelete="cascade", check_company=True)
    company_id = fields.Many2one(related="board_id.company_id", store=True)
    sequence = fields.Integer(default=10)
    metric = fields.Selection(METRIC_OPTIONS, default="pending", required=True)
    dimension = fields.Selection(DIMENSION_OPTIONS, default="city", required=True)
    chart_type = fields.Selection([("bar", "Barras"), ("table", "Tabla"), ("line", "Línea"), ("donut", "Distribución circular")], default="bar", required=True)
    top_n = fields.Integer(default=10)

    @api.constrains("top_n", "metric", "chart_type", "dimension")
    def _check_widget(self):
        for widget in self:
            if not 1 <= widget.top_n <= 50:
                raise ValidationError(_("El máximo de grupos debe estar entre 1 y 50."))
            if widget.chart_type == "line" and widget.dimension != "month":
                raise ValidationError(_("El gráfico de línea requiere la dimensión Mes de factura."))
            if widget.chart_type == "donut" and widget.metric not in ("total", "pending", "overdue", "pending_weight"):
                raise ValidationError(_("La distribución circular necesita una cantidad aditiva."))
