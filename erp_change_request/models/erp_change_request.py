from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError


class ErpChangeRequest(models.Model):
    _name = "erp.change.request"
    _description = "Solicitud de desarrollo o cambio ERP"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "priority desc, create_date desc, id desc"
    _check_company_auto = False

    name = fields.Char(
        string="Número", required=True, copy=False, readonly=True, default="Nuevo", index=True
    )
    title = fields.Char(string="Título", required=True, tracking=True, index=True)
    request_type = fields.Selection(
        [
            ("development", "Nuevo desarrollo"),
            ("change", "Cambio o mejora"),
            ("report", "Reporte o consulta"),
            ("integration", "Integración"),
            ("other", "Otro"),
        ],
        string="Tipo",
        required=True,
        default="change",
        tracking=True,
    )
    
    company_id = fields.Many2one(
        "res.partner",
        string="Empresa cliente",
        required=True,
        index=True,
        ondelete="cascade",
        domain="[('is_company', '=', True)]",
    )

    department_id = fields.Many2one(
        "erp.request.department",
        string="Departamento",
        required=True,
        domain="[('company_id', '=', company_id)]",
        tracking=True,
    )
    requester_id = fields.Many2one(
        "res.users",
        string="Solicitante",
        required=True,
        default=lambda self: self.env.user,
        index=True,
        tracking=True,
        check_company=False,
    )
    developer_id = fields.Many2one(
        "res.users",
        string="Asignado a",
        # domain="[('partner_id.parent_id', '=', company_id)]",
        index=True,
        tracking=True,
        check_company=False,
    )
    priority = fields.Selection(
        [("0", "Baja"), ("1", "Normal"), ("2", "Alta"), ("3", "Urgente")],
        default="1",
        required=True,
        tracking=True,
    )
    required_date = fields.Date(string="Fecha requerida", required=True, tracking=True)
    description = fields.Html(
        string="Descripción y necesidad",
        required=True,
        sanitize=True,
        help="Explique el problema actual, el cambio requerido y el resultado esperado.",
    )
    business_justification = fields.Html(string="Justificación o beneficio", sanitize=True)
    acceptance_criteria = fields.Html(
        string="Criterios de aceptación",
        sanitize=True,
        help="Condiciones concretas que deben cumplirse para aceptar el cambio.",
    )
    estimated_hours = fields.Float(string="Horas estimadas", tracking=True)
    actual_hours = fields.Float(string="Horas reales", tracking=True)
    review_notes = fields.Html(string="Análisis de Sistemas", sanitize=True)
    test_notes = fields.Html(string="Resultado de pruebas", sanitize=True)
    requester_approved = fields.Boolean(
        string="Conformidad del solicitante", copy=False, tracking=True
    )
    approval_date = fields.Datetime(string="Fecha de conformidad", readonly=True, copy=False)
    completed_date = fields.Datetime(string="Fecha de terminación", readonly=True, copy=False)
    attachment_count = fields.Integer(compute="_compute_attachment_count")
    state = fields.Selection(
        [
            ("requested", "Solicitado"),
            ("review", "Revisión"),
            ("approved", "Aprobado"),
            ("development", "Desarrollo"),
            ("testing", "Pruebas"),
            ("done", "Terminado"),
            ("cancelled", "Cancelado"),
        ],
        string="Estado",
        default="requested",
        required=True,
        copy=False,
        tracking=True,
        group_expand="_expand_states",
        index=True,
    )
    is_overdue = fields.Boolean(string="Vencida", compute="_compute_is_overdue", search="_search_is_overdue")
    days_open = fields.Integer(string="Días abiertos", compute="_compute_days_open")

    @api.model
    def _expand_states(self, states, domain):
        return [
            "requested", "review", "approved", "development", "testing", "done", "cancelled"
        ]

    @api.depends("required_date", "state")
    def _compute_is_overdue(self):
        today = fields.Date.context_today(self)
        for request in self:
            request.is_overdue = bool(
                request.required_date
                and request.required_date < today
                and request.state not in ("done", "cancelled")
            )

    def _search_is_overdue(self, operator, value):
        overdue_domain = [
            ("required_date", "<", fields.Date.context_today(self)),
            ("state", "not in", ("done", "cancelled")),
        ]
        return overdue_domain if (operator == "=" and value) or (operator == "!=" and not value) else ["!"] + overdue_domain

    @api.depends("create_date", "completed_date")
    def _compute_days_open(self):
        now = fields.Datetime.now()
        for request in self:
            start = request.create_date or now
            end = request.completed_date or now
            request.days_open = max((end.date() - start.date()).days, 0)

    def _compute_attachment_count(self):
        grouped = self.env["ir.attachment"]._read_group(
            [("res_model", "=", self._name), ("res_id", "in", self.ids)],
            ["res_id"],
            ["__count"],
        )
        counts = {res_id: count for res_id, count in grouped}
        for request in self:
            request.attachment_count = counts.get(request.id, 0)

    @api.constrains("estimated_hours", "actual_hours")
    def _check_hours(self):
        for request in self:
            if request.estimated_hours < 0 or request.actual_hours < 0:
                raise ValidationError(_("Las horas no pueden ser negativas."))

    # @api.constrains("department_id", "company_id")
    # def _check_department_company(self):
    #     for request in self:
    #         if request.department_id.company_id != request.company_id:
    #             raise ValidationError(_("El departamento debe pertenecer a la empresa cliente."))

    @api.constrains("department_id", "company_id")
    def _check_department_company(self):
        for request in self:
            if (
                request.department_id and request.company_id and request.department_id.company_id != request.company_id
            ):
                raise ValidationError(
                    _("El departamento debe pertenecer a la empresa cliente.")
                )

    @api.model_create_multi
    def create(self, vals_list):
        is_manager = self.env.user.has_group("erp_change_request.group_erp_request_manager")
        internal_fields = {
            "developer_id", "estimated_hours", "actual_hours", "review_notes", "test_notes",
            "requester_approved", "approval_date", "completed_date",
        }
        for vals in vals_list:
            if vals.get("name", "Nuevo") == "Nuevo":
                vals["name"] = self.env["ir.sequence"].next_by_code("erp.change.request") or "Nuevo"
            if not is_manager:
                for field_name in internal_fields:
                    vals.pop(field_name, None)
                vals["requester_id"] = self.env.user.id
                vals["state"] = "requested"
        records = super().create(vals_list)
        for record in records:
            record.message_subscribe(partner_ids=record.requester_id.partner_id.ids)
        return records

    def write(self, vals):
        protected = {"state", "developer_id", "estimated_hours", "actual_hours", "review_notes", "test_notes"}
        is_team = (
            self.env.user.has_group("erp_change_request.group_erp_request_team")
            or self.env.user.has_group("erp_change_request.group_erp_request_manager")
        )
        if protected.intersection(vals) and not is_team:
            if not self.env.context.get("erp_request_authorized_transition"):
                raise AccessError(_("Solo el equipo de Sistemas puede modificar la gestión interna."))
        if not is_team and not self.env.context.get("erp_request_authorized_transition"):
            allowed_requester_fields = {
                "title", "request_type", "company_id", "department_id", "priority",
                "required_date", "description", "business_justification", "acceptance_criteria",
                "message_follower_ids", "message_partner_ids",
            }
            forbidden = set(vals) - allowed_requester_fields
            if forbidden:
                raise AccessError(_("No puede modificar campos de control de la solicitud."))
            if any(request.state != "requested" for request in self):
                raise AccessError(_("La solicitud solo puede editarse mientras está en estado Solicitado."))
        result = super().write(vals)
        if "developer_id" in vals:
            for request in self.filtered("developer_id"):
                request.message_subscribe(partner_ids=request.developer_id.partner_id.ids)
        return result

    def _ensure_team(self):
        if not (
            self.env.user.has_group("erp_change_request.group_erp_request_team")
            or self.env.user.has_group("erp_change_request.group_erp_request_manager")
        ):
            raise AccessError(_("Esta acción corresponde al equipo de Sistemas."))

    def _set_state(self, new_state, message):
        self.ensure_one()
        self.with_context(erp_request_authorized_transition=True).write({"state": new_state})
        partners = (self.requester_id.partner_id | self.developer_id.partner_id).filtered("email")
        self.message_post(
            body=Markup("<p>%s</p>") % message,
            partner_ids=partners.ids,
            subtype_xmlid="mail.mt_comment",
        )

    def action_start_review(self):
        for request in self:
            request._ensure_team()
            if request.state != "requested":
                raise UserError(_("Solo se pueden revisar solicitudes nuevas."))
            request._set_state("review", _("La solicitud entró en revisión."))

    def action_approve(self):
        for request in self:
            request._ensure_team()
            if request.state != "review":
                raise UserError(_("La solicitud debe estar en revisión."))
            if not request.developer_id:
                raise UserError(_("Asigne un responsable antes de aprobar."))
            if request.estimated_hours <= 0:
                raise UserError(_("Registre las horas estimadas antes de aprobar."))
            request._set_state("approved", _("La solicitud fue aprobada y asignada."))
            request.activity_schedule(
                "mail.mail_activity_data_todo",
                user_id=request.developer_id.id,
                summary=_("Iniciar desarrollo: %s") % request.name,
                note=request.title,
                date_deadline=request.required_date,
            )

    def action_start_development(self):
        for request in self:
            request._ensure_team()
            if request.state != "approved":
                raise UserError(_("La solicitud debe estar aprobada."))
            request._set_state("development", _("Se inició el desarrollo."))

    def action_send_to_testing(self):
        for request in self:
            request._ensure_team()
            if request.state != "development":
                raise UserError(_("La solicitud debe estar en desarrollo."))
            request.requester_approved = False
            request.approval_date = False
            request._set_state("testing", _("El cambio está disponible para pruebas del solicitante."))
            request.activity_schedule(
                "mail.mail_activity_data_todo",
                user_id=request.requester_id.id,
                summary=_("Probar y aceptar: %s") % request.name,
                note=request.title,
                date_deadline=request.required_date,
            )

    def action_accept_and_close(self):
        for request in self:
            if request.state != "testing":
                raise UserError(_("La solicitud debe estar en pruebas."))
            is_requester = request.requester_id == self.env.user
            is_manager = self.env.user.has_group("erp_change_request.group_erp_request_manager")
            if not (is_requester or is_manager):
                raise AccessError(_("Solo el solicitante o un administrador puede dar la conformidad."))
            request.with_context(erp_request_authorized_transition=True).write({
                "requester_approved": True,
                "approval_date": fields.Datetime.now(),
                "completed_date": fields.Datetime.now(),
            })
            request._set_state("done", _("El solicitante aceptó el cambio. Solicitud terminada."))
            request.activity_ids.filtered(lambda a: a.user_id == request.requester_id).action_feedback(
                feedback=_("Cambio probado y aceptado.")
            )

    def action_return_to_development(self):
        for request in self:
            if request.state != "testing":
                raise UserError(_("La solicitud debe estar en pruebas."))
            if request.requester_id != self.env.user and not self.env.user.has_group(
                "erp_change_request.group_erp_request_manager"
            ):
                raise AccessError(_("Solo el solicitante puede devolver el cambio."))
            request.with_context(erp_request_authorized_transition=True).write({
                "requester_approved": False,
                "approval_date": False,
            })
            request._set_state("development", _("El solicitante reportó ajustes y devolvió la solicitud a desarrollo."))

    def action_cancel(self):
        for request in self:
            request._ensure_team()
            if request.state == "done":
                raise UserError(_("No se puede cancelar una solicitud terminada."))
            request._set_state("cancelled", _("La solicitud fue cancelada."))

    def action_reopen(self):
        for request in self:
            if not self.env.user.has_group("erp_change_request.group_erp_request_manager"):
                raise AccessError(_("Solo un administrador puede reabrir solicitudes."))
            request.write({
                "state": "review",
                "requester_approved": False,
                "approval_date": False,
                "completed_date": False,
            })
            request.message_post(body=_("La solicitud fue reabierta para revisión."))

    def action_view_attachments(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Archivos y capturas"),
            "res_model": "ir.attachment",
            "view_mode": "kanban,list,form",
            "domain": [("res_model", "=", self._name), ("res_id", "=", self.id)],
            "context": {"default_res_model": self._name, "default_res_id": self.id},
        }
