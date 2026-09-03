import base64
import re
import secrets

from odoo import api, fields, models, tools, _
from odoo.exceptions import ValidationError


class DigitalTrainingAttendee(models.Model):
    _name = "digital.training.attendee"
    _description = "Participante de capacitación"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "registered_at desc, id desc"

    event_id = fields.Many2one(
        "digital.training.event",
        string="Capacitación",
        required=True,
        ondelete="cascade",
        index=True,
        tracking=True,
    )
    full_name = fields.Char(string="Nombres completos", required=True, tracking=True)
    email = fields.Char(string="Correo electrónico", required=True, index=True, tracking=True)
    organization_id = fields.Many2one(
        "digital.training.organization",
        string="Empresa",
        required=True,
        ondelete="restrict",
        tracking=True,
    )
    registered_at = fields.Datetime(
        string="Fecha y hora de registro",
        required=True,
        default=fields.Datetime.now,
        readonly=True,
    )
    certificate_number = fields.Char(
        string="Número de certificado", readonly=True, copy=False, index=True
    )
    download_token = fields.Char(string="Token de descarga", readonly=True, copy=False, index=True)
    certificate_attachment_id = fields.Many2one(
        "ir.attachment",
        string="Certificado PDF",
        readonly=True,
        copy=False,
        ondelete="set null",
    )
    email_state = fields.Selection(
        [("pending", "Pendiente"), ("sent", "Enviado"), ("error", "Error")],
        string="Estado del correo",
        default="pending",
        required=True,
        readonly=True,
        tracking=True,
    )
    email_sent_at = fields.Datetime(string="Correo enviado el", readonly=True, copy=False)
    email_error = fields.Text(string="Detalle del error", readonly=True, copy=False)

    _sql_constraints = [
        (
            "attendee_event_email_unique",
            "unique(event_id, email)",
            "Este correo ya se registró en la capacitación.",
        ),
        (
            "attendee_certificate_number_unique",
            "unique(certificate_number)",
            "El número de certificado debe ser único.",
        ),
        (
            "attendee_download_token_unique",
            "unique(download_token)",
            "El token de descarga debe ser único.",
        ),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        sequence = self.env["ir.sequence"]
        for vals in vals_list:
            vals["full_name"] = " ".join((vals.get("full_name") or "").split())
            normalized_email = tools.email_normalize(vals.get("email") or "")
            if not normalized_email:
                raise ValidationError(_("Ingrese un correo electrónico válido."))
            vals["email"] = normalized_email.lower()
            if not vals.get("certificate_number"):
                vals["certificate_number"] = sequence.next_by_code(
                    "digital.training.certificate"
                )
            if not vals.get("download_token"):
                vals["download_token"] = secrets.token_urlsafe(32)
        records = super().create(vals_list)
        records._validate_organization_for_event()
        return records

    @api.constrains("full_name")
    def _check_full_name(self):
        for attendee in self:
            if len(attendee.full_name or "") < 3 or len(attendee.full_name) > 150:
                raise ValidationError(
                    _("Los nombres completos deben contener entre 3 y 150 caracteres.")
                )

    def write(self, vals):
        if "full_name" in vals:
            vals["full_name"] = " ".join((vals.get("full_name") or "").split())
        if "email" in vals:
            normalized_email = tools.email_normalize(vals.get("email") or "")
            if not normalized_email:
                raise ValidationError(_("Ingrese un correo electrónico válido."))
            vals["email"] = normalized_email.lower()
        result = super().write(vals)
        if "event_id" in vals or "organization_id" in vals:
            self._validate_organization_for_event()
        return result

    def _validate_organization_for_event(self):
        for attendee in self:
            if attendee.organization_id not in attendee.event_id.organization_ids:
                raise ValidationError(
                    _("La empresa seleccionada no está habilitada para esta capacitación.")
                )

    def get_certificate_body_html(self):
        self.ensure_one()
        return self.event_id.certificate_template_id.render_certificate_body(self)

    def get_certificate_footer_html(self):
        self.ensure_one()
        return self.event_id.certificate_template_id.render_certificate_footer(self)

    def _certificate_filename(self):
        self.ensure_one()
        safe_number = re.sub(r"[^A-Za-z0-9_-]+", "_", self.certificate_number or str(self.id))
        return "Certificado_%s.pdf" % safe_number

    def action_generate_certificate(self):
        report_service = self.env["ir.actions.report"].sudo()
        for attendee in self:
            pdf_content, _content_type = report_service._render_qweb_pdf(
                "digital_training_certificate.report_training_certificate",
                res_ids=attendee.ids,
            )
            values = {
                "name": attendee._certificate_filename(),
                "type": "binary",
                "datas": base64.b64encode(pdf_content),
                "mimetype": "application/pdf",
                "res_model": attendee._name,
                "res_id": attendee.id,
            }
            if attendee.certificate_attachment_id:
                attendee.certificate_attachment_id.sudo().write(values)
                attachment = attendee.certificate_attachment_id
            else:
                attachment = self.env["ir.attachment"].sudo().create(values)
                attendee.sudo().certificate_attachment_id = attachment
        return True

    def _get_email_from(self):
        self.ensure_one()
        return (
            self.event_id.email_from
            or self.env.company.email_formatted
            or self.env.user.email_formatted
        )

    def action_send_certificate(self):
        for attendee in self:
            if not attendee.certificate_attachment_id:
                attendee.action_generate_certificate()
            email_from = attendee._get_email_from()
            if not email_from:
                attendee.sudo().write(
                    {
                        "email_state": "error",
                        "email_error": _(
                            "Configure el correo del remitente en la capacitación o en la empresa de Odoo."
                        ),
                    }
                )
                continue
            template = attendee.event_id.certificate_template_id
            mail = self.env["mail.mail"].sudo().create(
                {
                    "subject": template.render_email_subject(attendee),
                    "body_html": template.render_email_body(attendee),
                    "email_from": email_from,
                    "email_to": attendee.email,
                    "model": attendee._name,
                    "res_id": attendee.id,
                    "attachment_ids": [(4, attendee.certificate_attachment_id.id)],
                    "auto_delete": False,
                }
            )
            try:
                mail.send(raise_exception=True)
                attendee.sudo().write(
                    {
                        "email_state": "sent",
                        "email_sent_at": fields.Datetime.now(),
                        "email_error": False,
                    }
                )
            except Exception as error:
                attendee.sudo().write(
                    {
                        "email_state": "error",
                        "email_error": str(error)[:2000],
                    }
                )
        return True

    def action_generate_and_send_certificate(self):
        for attendee in self:
            try:
                attendee.action_generate_certificate()
                attendee.action_send_certificate()
            except Exception as error:
                attendee.sudo().write(
                    {
                        "email_state": "error",
                        "email_error": str(error)[:2000],
                    }
                )
        return True

    def action_download_certificate(self):
        self.ensure_one()
        if not self.certificate_attachment_id:
            self.action_generate_certificate()
        return {
            "type": "ir.actions.act_url",
            "url": "/web/content/%s?download=true" % self.certificate_attachment_id.id,
            "target": "self",
        }
