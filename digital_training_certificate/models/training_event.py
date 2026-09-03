import secrets
from urllib.parse import quote_plus

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class DigitalTrainingEvent(models.Model):
    _name = "digital.training.event"
    _description = "Evento de capacitación"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "event_date desc, id desc"

    name = fields.Char(string="Nombre de la capacitación", required=True, tracking=True)
    code = fields.Char(string="Código", readonly=True, copy=False, default="Nuevo")
    course_id = fields.Many2one(
        "digital.training.course",
        string="Curso",
        required=True,
        ondelete="restrict",
        tracking=True,
    )
    event_date = fields.Date(
        string="Fecha",
        required=True,
        default=fields.Date.context_today,
        tracking=True,
    )
    duration_hours = fields.Float(string="Duración (horas)", required=True, default=1.0)
    instructor_name = fields.Char(string="Facilitador / instructor", required=True)
    organization_ids = fields.Many2many(
        "digital.training.organization",
        "digital_training_event_organization_rel",
        "event_id",
        "organization_id",
        string="Empresas disponibles",
        required=True,
    )
    certificate_template_id = fields.Many2one(
        "digital.training.certificate.template",
        string="Plantilla del certificado",
        required=True,
        ondelete="restrict",
        default=lambda self: self.env["digital.training.certificate.template"].search(
            [("active", "=", True)], limit=1
        ),
    )
    form_title = fields.Char(
        string="Título del formulario",
        default="Registro de participación",
        required=True,
    )
    form_intro = fields.Html(
        string="Texto introductorio",
        default="<p>Complete sus datos para recibir automáticamente su certificado.</p>",
        sanitize=True,
    )
    success_message = fields.Html(
        string="Mensaje de confirmación",
        default="<p>Su registro fue recibido correctamente.</p>",
        sanitize=True,
    )
    privacy_notice = fields.Html(
        string="Aviso de privacidad",
        default=(
            "<p>Los datos ingresados se utilizarán únicamente para registrar su "
            "participación y emitir el certificado.</p>"
        ),
        sanitize=True,
    )
    registration_start = fields.Datetime(string="Registro habilitado desde")
    registration_end = fields.Datetime(string="Registro habilitado hasta")
    public_base_url = fields.Char(
        string="URL pública alternativa",
        help=(
            "Déjelo vacío para utilizar la URL base de Odoo. Úselo cuando Odoo tenga "
            "configurada una dirección interna diferente al dominio público."
        ),
    )
    email_from = fields.Char(
        string="Remitente del correo",
        help="Opcional. Ejemplo: Capacitaciones <capacitaciones@empresa.com>.",
    )
    state = fields.Selection(
        [("draft", "Borrador"), ("open", "Registro abierto"), ("closed", "Cerrado")],
        string="Estado",
        default="draft",
        required=True,
        tracking=True,
    )
    access_token = fields.Char(string="Token público", readonly=True, copy=False, index=True)
    public_url = fields.Char(string="Enlace del formulario", compute="_compute_public_urls")
    qr_image_url = fields.Char(string="Imagen QR", compute="_compute_public_urls")
    attendee_ids = fields.One2many(
        "digital.training.attendee", "event_id", string="Participantes"
    )
    attendee_count = fields.Integer(compute="_compute_counts", string="Participantes")
    email_sent_count = fields.Integer(compute="_compute_counts", string="Correos enviados")

    _sql_constraints = [
        ("event_access_token_unique", "unique(access_token)", "El token del evento debe ser único."),
        ("event_duration_positive", "CHECK(duration_hours > 0)", "La duración debe ser mayor que cero."),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        sequence = self.env["ir.sequence"]
        for vals in vals_list:
            if not vals.get("access_token"):
                vals["access_token"] = secrets.token_urlsafe(24)
            if not vals.get("code") or vals.get("code") == "Nuevo":
                vals["code"] = sequence.next_by_code("digital.training.event") or "Nuevo"
        return super().create(vals_list)

    @api.onchange("course_id")
    def _onchange_course_id(self):
        if self.course_id:
            self.duration_hours = self.course_id.default_duration_hours

    @api.depends("access_token", "public_base_url")
    def _compute_public_urls(self):
        system_base_url = self.env["ir.config_parameter"].sudo().get_param("web.base.url", "")
        for event in self:
            base_url = (event.public_base_url or system_base_url or "").rstrip("/")
            if event.access_token and base_url:
                event.public_url = "%s/capacitacion/%s" % (base_url, event.access_token)
                event.qr_image_url = (
                    "/report/barcode/?barcode_type=QR&value=%s&width=500&height=500"
                    % quote_plus(event.public_url)
                )
            else:
                event.public_url = False
                event.qr_image_url = False

    @api.depends("attendee_ids", "attendee_ids.email_state")
    def _compute_counts(self):
        for event in self:
            event.attendee_count = len(event.attendee_ids)
            event.email_sent_count = len(
                event.attendee_ids.filtered(lambda attendee: attendee.email_state == "sent")
            )

    @api.constrains("registration_start", "registration_end")
    def _check_registration_window(self):
        for event in self:
            if (
                event.registration_start
                and event.registration_end
                and event.registration_end < event.registration_start
            ):
                raise ValidationError(
                    _("La fecha de cierre no puede ser anterior a la fecha de apertura.")
                )

    @api.constrains("organization_ids")
    def _check_organizations(self):
        for event in self:
            if not event.organization_ids:
                raise ValidationError(_("Seleccione al menos una empresa participante."))

    @property
    def certificate_date_label(self):
        self.ensure_one()
        return self.event_date.strftime("%d/%m/%Y") if self.event_date else ""

    @property
    def duration_label(self):
        self.ensure_one()
        duration = ("%.2f" % self.duration_hours).rstrip("0").rstrip(".")
        return "%s hora%s" % (duration, "s" if self.duration_hours != 1 else "")

    def get_registration_availability(self):
        self.ensure_one()
        now = fields.Datetime.now()
        if self.state != "open":
            return False, _("El registro de esta capacitación no está habilitado.")
        if self.registration_start and now < self.registration_start:
            return False, _("El registro todavía no se encuentra habilitado.")
        if self.registration_end and now > self.registration_end:
            return False, _("El periodo de registro ha finalizado.")
        return True, ""

    def action_open_registration(self):
        for event in self:
            if not event.organization_ids.filtered("active"):
                raise ValidationError(
                    _("Debe habilitar al menos una empresa participante activa.")
                )
        self.write({"state": "open"})

    def action_close_registration(self):
        self.write({"state": "closed"})

    def action_reset_to_draft(self):
        self.write({"state": "draft"})

    def action_regenerate_token(self):
        for event in self:
            event.access_token = secrets.token_urlsafe(24)
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("QR actualizado"),
                "message": _("El enlace anterior dejó de ser válido."),
                "type": "success",
                "sticky": False,
            },
        }

    def action_open_public_form(self):
        self.ensure_one()
        return {"type": "ir.actions.act_url", "url": self.public_url, "target": "new"}

    def action_show_qr(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_url",
            "url": "/capacitacion/evento/%s/qr" % self.id,
            "target": "new",
        }

    def action_view_attendees(self):
        self.ensure_one()
        action = self.env.ref(
            "digital_training_certificate.action_digital_training_attendee"
        ).read()[0]
        action["domain"] = [("event_id", "=", self.id)]
        action["context"] = {"default_event_id": self.id}
        return action
