from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class ResPartner(models.Model):
    _inherit = "res.partner"

    is_route_customer = fields.Boolean(string="Cliente de ruta", tracking=True)
    establishment_type = fields.Selection([
        ("main", "Matriz"), ("store", "Tienda/Sucursal"), ("warehouse", "Bodega"),
    ], string="Tipo de establecimiento")
    commercial_sector = fields.Selection([
        ("traditional", "Canal tradicional"), ("modern", "Canal moderno"),
        ("wholesale", "Mayorista"), ("horeca", "HORECA"),
        ("institutional", "Institucional"), ("other", "Otro"),
    ], string="Sector comercial", tracking=True)
    market_segment = fields.Char(string="Segmento/Subsector")
    zone = fields.Char(string="Zona comercial", tracking=True)
    route_reference = fields.Char(string="Referencia de ubicación")
    opening_hours = fields.Char(string="Horario de atención")
    visit_frequency = fields.Selection([
        ("weekly", "Semanal"), ("biweekly", "Quincenal"),
        ("monthly", "Mensual"), ("custom", "Personalizada"),
    ], string="Frecuencia de visita")
    preferred_visit_day = fields.Selection([
        ("0", "Lunes"), ("1", "Martes"), ("2", "Miércoles"),
        ("3", "Jueves"), ("4", "Viernes"), ("5", "Sábado"), ("6", "Domingo"),
    ], string="Día preferido")
    assigned_salesperson_id = fields.Many2one("res.users", string="Vendedor rutero", domain="[('share','=',False)]", tracking=True)
    latitude = fields.Float(digits=(10, 7), string="Latitud")
    longitude = fields.Float(digits=(10, 7), string="Longitud")
    store_count = fields.Integer(compute="_compute_store_count", string="N.º de tiendas")
    route_visit_ids = fields.One2many("route.sale.visit", "partner_id", string="Visitas de ruta")
    route_visit_count = fields.Integer(compute="_compute_route_visit_count")
    last_route_visit = fields.Datetime(compute="_compute_last_route_visit")
    competitor_notes = fields.Text(string="Observaciones de competencia")
    customer_potential = fields.Selection([
        ("low", "Bajo"), ("medium", "Medio"), ("high", "Alto"), ("strategic", "Estratégico"),
    ], string="Potencial comercial")

    @api.depends("child_ids", "child_ids.establishment_type")
    def _compute_store_count(self):
        for partner in self:
            partner.store_count = len(partner.child_ids.filtered(lambda p: p.establishment_type == "store"))

    @api.depends("route_visit_ids")
    def _compute_route_visit_count(self):
        for partner in self:
            partner.route_visit_count = len(partner.route_visit_ids)

    def _compute_last_route_visit(self):
        for partner in self:
            partner.last_route_visit = max(partner.route_visit_ids.mapped("checkin_at"), default=False)

    def action_open_route_visits(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window", "name": _("Visitas"),
            "res_model": "route.sale.visit", "view_mode": "list,form,kanban,pivot,graph",
            "domain": [("partner_id", "=", self.id)],
            "context": {"default_partner_id": self.id, "default_salesperson_id": self.assigned_salesperson_id.id},
        }


class RoutePlan(models.Model):
    _name = "route.sale.plan"
    _description = "Plan de ruta comercial"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "date desc, id desc"

    name = fields.Char(default="Nuevo", readonly=True, copy=False)
    date = fields.Date(required=True, default=fields.Date.context_today, tracking=True)
    salesperson_id = fields.Many2one("res.users", required=True, default=lambda self: self.env.user, tracking=True)
    zone = fields.Char(tracking=True)
    visit_ids = fields.One2many("route.sale.visit", "route_id", string="Visitas")
    planned_count = fields.Integer(compute="_compute_counts")
    completed_count = fields.Integer(compute="_compute_counts")
    state = fields.Selection([
        ("draft", "Borrador"), ("planned", "Planificada"),
        ("in_progress", "En curso"), ("done", "Finalizada"), ("cancelled", "Anulada"),
    ], default="draft", tracking=True)
    notes = fields.Text()

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "Nuevo") == "Nuevo":
                vals["name"] = self.env["ir.sequence"].next_by_code("route.sale.plan") or "Nuevo"
        return super().create(vals_list)

    @api.depends("visit_ids", "visit_ids.state")
    def _compute_counts(self):
        for rec in self:
            rec.planned_count = len(rec.visit_ids)
            rec.completed_count = len(rec.visit_ids.filtered(lambda v: v.state == "done"))

    def action_plan(self):
        if any(not rec.visit_ids for rec in self):
            raise ValidationError(_("Agregue al menos una visita a la ruta."))
        self.write({"state": "planned"})

    def action_start(self):
        self.write({"state": "in_progress"})

    def action_done(self):
        if any(rec.visit_ids.filtered(lambda v: v.state == "checked_in") for rec in self):
            raise ValidationError(_("Existen visitas que aún no registran salida."))
        self.write({"state": "done"})

    def action_cancel(self):
        self.write({"state": "cancelled"})


class RouteSaleVisit(models.Model):
    _name = "route.sale.visit"
    _description = "Visita comercial de ruta"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "planned_at desc, sequence, id desc"

    name = fields.Char(default="Nuevo", readonly=True, copy=False)
    sequence = fields.Integer(default=10)
    route_id = fields.Many2one("route.sale.plan", ondelete="set null", tracking=True)
    salesperson_id = fields.Many2one("res.users", required=True, default=lambda self: self.env.user, tracking=True)
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company)
    partner_id = fields.Many2one("res.partner", string="Tienda/Cliente", required=True, domain="[('is_route_customer','=',True)]", tracking=True)
    commercial_partner_id = fields.Many2one(related="partner_id.commercial_partner_id", store=True, string="Cliente principal")
    crm_lead_id = fields.Many2one("crm.lead", string="Oportunidad CRM")
    planned_at = fields.Datetime(string="Fecha planificada", required=True, default=fields.Datetime.now, tracking=True)
    checkin_at = fields.Datetime(string="Entrada", readonly=True, tracking=True)
    checkout_at = fields.Datetime(string="Salida", readonly=True, tracking=True)
    checkin_latitude = fields.Float(digits=(10, 7), readonly=True)
    checkin_longitude = fields.Float(digits=(10, 7), readonly=True)
    checkin_accuracy = fields.Float(string="Precisión entrada (m)", readonly=True)
    checkout_latitude = fields.Float(digits=(10, 7), readonly=True)
    checkout_longitude = fields.Float(digits=(10, 7), readonly=True)
    checkout_accuracy = fields.Float(string="Precisión salida (m)", readonly=True)
    duration_minutes = fields.Float(compute="_compute_duration", string="Duración (min)")
    checkin_map_url = fields.Char(compute="_compute_map_urls")
    checkout_map_url = fields.Char(compute="_compute_map_urls")
    visit_photo_ids = fields.Many2many("ir.attachment", "route_visit_photo_rel", "visit_id", "attachment_id", string="Fotos del establecimiento")
    evidence_ids = fields.Many2many("ir.attachment", "route_visit_evidence_rel", "visit_id", "attachment_id", string="Otras evidencias")
    result = fields.Selection([
        ("quotation", "Cotización"), ("order", "Pedido"), ("collection", "Cobranza"),
        ("followup", "Seguimiento"), ("no_contact", "No atendido"), ("closed", "Sin oportunidad"),
    ], string="Resultado")
    outcome_notes = fields.Text(string="Resultado y observaciones")
    next_visit_at = fields.Datetime(string="Próxima visita")
    survey_line_ids = fields.One2many("route.visit.survey.line", "visit_id", string="Encuesta comercial")
    competitor_line_ids = fields.One2many("route.visit.competitor", "visit_id", string="Competencia")
    collection_ids = fields.One2many("route.visit.collection", "visit_id", string="Cobranzas")
    collection_total = fields.Monetary(compute="_compute_collection_total")
    currency_id = fields.Many2one(related="company_id.currency_id", store=True)
    sale_order_ids = fields.One2many("sale.order", "route_visit_id", string="Cotizaciones/Pedidos")
    quotation_count = fields.Integer(compute="_compute_quotation_count")
    state = fields.Selection([
        ("planned", "Planificada"), ("checked_in", "En visita"),
        ("done", "Finalizada"), ("cancelled", "Cancelada"),
    ], default="planned", tracking=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "Nuevo") == "Nuevo":
                vals["name"] = self.env["ir.sequence"].next_by_code("route.sale.visit") or "Nuevo"
        return super().create(vals_list)

    @api.depends("checkin_at", "checkout_at")
    def _compute_duration(self):
        for rec in self:
            rec.duration_minutes = (rec.checkout_at - rec.checkin_at).total_seconds() / 60 if rec.checkin_at and rec.checkout_at else 0

    @api.depends("checkin_latitude", "checkin_longitude", "checkout_latitude", "checkout_longitude")
    def _compute_map_urls(self):
        for rec in self:
            rec.checkin_map_url = "https://www.google.com/maps?q=%s,%s" % (rec.checkin_latitude, rec.checkin_longitude) if rec.checkin_latitude and rec.checkin_longitude else False
            rec.checkout_map_url = "https://www.google.com/maps?q=%s,%s" % (rec.checkout_latitude, rec.checkout_longitude) if rec.checkout_latitude and rec.checkout_longitude else False

    @api.depends("collection_ids.amount")
    def _compute_collection_total(self):
        for rec in self:
            rec.collection_total = sum(rec.collection_ids.mapped("amount"))

    @api.depends("sale_order_ids")
    def _compute_quotation_count(self):
        for rec in self:
            rec.quotation_count = len(rec.sale_order_ids)

    def action_capture_checkin(self):
        self.ensure_one()
        if self.state != "planned":
            raise UserError(_("La visita no está disponible para registrar entrada."))
        return {"type": "ir.actions.client", "tag": "route_sales_crm.gps_capture", "params": {"visit_id": self.id, "mode": "checkin"}}

    def action_capture_checkout(self):
        self.ensure_one()
        if self.state != "checked_in":
            raise UserError(_("Primero debe registrar la entrada."))
        if not self.result or not self.outcome_notes:
            raise ValidationError(_("Registre el resultado y las observaciones antes de marcar la salida."))
        if not self.visit_photo_ids:
            raise ValidationError(_("Adjunte al menos una foto del establecimiento antes de marcar la salida."))
        if any(not collection.evidence_ids for collection in self.collection_ids):
            raise ValidationError(_("Toda cobranza debe tener al menos una evidencia adjunta."))
        return {"type": "ir.actions.client", "tag": "route_sales_crm.gps_capture", "params": {"visit_id": self.id, "mode": "checkout"}}

    def save_gps_position(self, mode, latitude, longitude, accuracy):
        self.ensure_one()
        if self.salesperson_id != self.env.user and not self.env.user.has_group("route_sales_crm.group_route_manager"):
            raise UserError(_("No puede registrar la ubicación de otra persona."))
        if mode == "checkin":
            if self.state != "planned":
                raise UserError(_("La entrada ya fue registrada o la visita no está disponible."))
            self.write({"checkin_at": fields.Datetime.now(), "checkin_latitude": latitude, "checkin_longitude": longitude, "checkin_accuracy": accuracy, "state": "checked_in"})
        elif mode == "checkout":
            if self.state != "checked_in":
                raise UserError(_("La visita no tiene una entrada activa."))
            self.write({"checkout_at": fields.Datetime.now(), "checkout_latitude": latitude, "checkout_longitude": longitude, "checkout_accuracy": accuracy, "state": "done"})
            if self.next_visit_at:
                self.activity_schedule("mail.mail_activity_data_todo", date_deadline=self.next_visit_at.date(), user_id=self.salesperson_id.id, summary=_("Próxima visita a %s") % self.partner_id.display_name)
        else:
            raise ValidationError(_("Modo GPS no reconocido."))
        return True

    def action_create_quotation(self):
        self.ensure_one()
        order = self.env["sale.order"].create({
            "partner_id": self.partner_id.id,
            "user_id": self.salesperson_id.id,
            "opportunity_id": self.crm_lead_id.id,
            "route_visit_id": self.id,
            "origin": self.name,
        })
        return {"type": "ir.actions.act_window", "res_model": "sale.order", "res_id": order.id, "view_mode": "form", "target": "current"}

    def action_open_quotations(self):
        self.ensure_one()
        return {"type": "ir.actions.act_window", "name": _("Cotizaciones y pedidos"), "res_model": "sale.order", "view_mode": "list,form", "domain": [("route_visit_id", "=", self.id)], "context": {"default_route_visit_id": self.id, "default_partner_id": self.partner_id.id}}

    def action_cancel(self):
        self.write({"state": "cancelled"})


class RouteVisitSurveyLine(models.Model):
    _name = "route.visit.survey.line"
    _description = "Respuesta de encuesta comercial"
    _order = "sequence, id"

    sequence = fields.Integer(default=10)
    visit_id = fields.Many2one("route.sale.visit", required=True, ondelete="cascade")
    question = fields.Char(string="Pregunta/Indicador", required=True)
    answer = fields.Char(string="Respuesta", required=True)
    notes = fields.Char(string="Observación")


class RouteVisitCompetitor(models.Model):
    _name = "route.visit.competitor"
    _description = "Competencia encontrada en visita"

    visit_id = fields.Many2one("route.sale.visit", required=True, ondelete="cascade")
    competitor = fields.Char(string="Competidor/Marca", required=True)
    product = fields.Char(string="Producto")
    price = fields.Monetary(string="Precio observado")
    currency_id = fields.Many2one(related="visit_id.currency_id", store=True)
    promotion = fields.Char(string="Promoción")
    shelf_presence = fields.Selection([("low", "Baja"), ("medium", "Media"), ("high", "Alta")], string="Presencia")
    notes = fields.Char(string="Observación")
    photo_ids = fields.Many2many("ir.attachment", "route_competitor_photo_rel", "line_id", "attachment_id", string="Fotos")


class RouteVisitCollection(models.Model):
    _name = "route.visit.collection"
    _description = "Cobranza registrada en visita"
    _order = "date desc, id desc"

    visit_id = fields.Many2one("route.sale.visit", required=True, ondelete="cascade")
    date = fields.Date(default=fields.Date.context_today, required=True)
    reference = fields.Char(string="Factura/Referencia", required=True)
    method = fields.Selection([("cash", "Efectivo"), ("transfer", "Transferencia"), ("check", "Cheque"), ("card", "Tarjeta"), ("other", "Otro")], required=True)
    amount = fields.Monetary(required=True)
    currency_id = fields.Many2one(related="visit_id.currency_id", store=True)
    notes = fields.Char()
    evidence_ids = fields.Many2many("ir.attachment", "route_collection_evidence_rel", "collection_id", "attachment_id", string="Evidencia")

    @api.constrains("amount", "evidence_ids")
    def _check_collection(self):
        for rec in self:
            if rec.amount <= 0:
                raise ValidationError(_("El valor cobrado debe ser mayor que cero."))


class SaleOrder(models.Model):
    _inherit = "sale.order"

    route_visit_id = fields.Many2one("route.sale.visit", string="Visita de ruta", copy=False, index=True)
