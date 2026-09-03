from markupsafe import Markup, escape

from odoo import fields, models


PLACEHOLDER_HELP = (
    "Variables disponibles: [NOMBRE], [CORREO], [EMPRESA], [CURSO], [FECHA], "
    "[DURACION], [INSTRUCTOR] y [CERTIFICADO]."
)


class DigitalTrainingCertificateTemplate(models.Model):
    _name = "digital.training.certificate.template"
    _description = "Plantilla de certificado"
    _order = "name"

    name = fields.Char(string="Plantilla", required=True)
    active = fields.Boolean(default=True)

    logo_primary = fields.Image(
        string="Logo principal",
        max_width=1600,
        max_height=1600,
        attachment=True,
    )
    logo_secondary = fields.Image(
        string="Logo secundario",
        max_width=1600,
        max_height=1600,
        attachment=True,
    )
    background_image = fields.Image(
        string="Fondo del certificado",
        max_width=2400,
        max_height=1800,
        attachment=True,
        help="Imagen opcional que ocupará toda la hoja A4 horizontal.",
    )
    show_organization_logo = fields.Boolean(
        string="Mostrar logo de la empresa del empleado",
        default=True,
    )
    primary_color = fields.Char(
        string="Color principal",
        default="#123B5D",
        required=True,
        help="Color hexadecimal, por ejemplo #123B5D.",
    )
    accent_color = fields.Char(
        string="Color de acento",
        default="#D6A84B",
        required=True,
        help="Color hexadecimal, por ejemplo #D6A84B.",
    )

    certificate_title = fields.Char(
        string="Título del certificado",
        default="CERTIFICADO DE PARTICIPACIÓN",
        required=True,
    )
    body_html = fields.Html(
        string="Texto del certificado",
        required=True,
        sanitize=True,
        help=PLACEHOLDER_HELP,
    )
    footer_html = fields.Html(
        string="Texto inferior",
        sanitize=True,
        help=PLACEHOLDER_HELP,
    )

    signature_1_image = fields.Image(
        string="Firma 1",
        max_width=1200,
        max_height=600,
        attachment=True,
    )
    signature_1_name = fields.Char(string="Nombre firmante 1")
    signature_1_title = fields.Char(string="Cargo firmante 1")
    signature_2_image = fields.Image(
        string="Firma 2",
        max_width=1200,
        max_height=600,
        attachment=True,
    )
    signature_2_name = fields.Char(string="Nombre firmante 2")
    signature_2_title = fields.Char(string="Cargo firmante 2")

    email_subject = fields.Char(
        string="Asunto del correo",
        default="Su certificado de [CURSO]",
        required=True,
        help=PLACEHOLDER_HELP,
    )
    email_body_html = fields.Html(
        string="Mensaje del correo",
        required=True,
        sanitize=True,
        help=PLACEHOLDER_HELP,
    )

    _sql_constraints = [
        ("template_name_unique", "unique(name)", "Ya existe una plantilla con este nombre."),
    ]

    def _placeholder_values(self, attendee):
        attendee.ensure_one()
        return {
            "[NOMBRE]": attendee.full_name or "",
            "[CORREO]": attendee.email or "",
            "[EMPRESA]": attendee.organization_id.name or "",
            "[CURSO]": attendee.event_id.course_id.name or "",
            "[FECHA]": attendee.event_id.certificate_date_label or "",
            "[DURACION]": attendee.event_id.duration_label or "",
            "[INSTRUCTOR]": attendee.event_id.instructor_name or "",
            "[CERTIFICADO]": attendee.certificate_number or "",
        }

    def _render_placeholders(self, value, attendee, html=False):
        self.ensure_one()
        rendered = str(value or "")
        for placeholder, replacement in self._placeholder_values(attendee).items():
            safe_replacement = str(escape(replacement)) if html else replacement
            rendered = rendered.replace(placeholder, safe_replacement)
        return Markup(rendered) if html else rendered

    def render_certificate_body(self, attendee):
        return self._render_placeholders(self.body_html, attendee, html=True)

    def render_certificate_footer(self, attendee):
        return self._render_placeholders(self.footer_html, attendee, html=True)

    def render_email_subject(self, attendee):
        return self._render_placeholders(self.email_subject, attendee, html=False)

    def render_email_body(self, attendee):
        return self._render_placeholders(self.email_body_html, attendee, html=True)

