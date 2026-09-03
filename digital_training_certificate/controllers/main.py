import base64

from psycopg2 import IntegrityError

from odoo import http, tools
from odoo.http import content_disposition, request


class DigitalTrainingCertificateController(http.Controller):
    def _find_event(self, token):
        return request.env["digital.training.event"].sudo().search(
            [("access_token", "=", token)], limit=1
        )

    @http.route(
        "/capacitacion/<string:token>",
        type="http",
        auth="public",
        website=False,
        sitemap=False,
        methods=["GET"],
    )
    def training_registration(self, token, **kwargs):
        event = self._find_event(token)
        if not event:
            return request.render(
                "digital_training_certificate.registration_unavailable",
                {"message": "El enlace de registro no es válido."},
            )
        available, message = event.get_registration_availability()
        return request.render(
            "digital_training_certificate.training_registration_page",
            {
                "event": event,
                "organizations": event.organization_ids.filtered("active"),
                "available": available,
                "availability_message": message,
                "errors": [],
                "form_data": {},
            },
        )

    @http.route(
        "/capacitacion/<string:token>/registrar",
        type="http",
        auth="public",
        website=False,
        sitemap=False,
        csrf=True,
        methods=["POST"],
    )
    def training_registration_submit(self, token, **post):
        event = self._find_event(token)
        if not event:
            return request.render(
                "digital_training_certificate.registration_unavailable",
                {"message": "El enlace de registro no es válido."},
            )

        available, message = event.get_registration_availability()
        full_name = " ".join((post.get("full_name") or "").split())
        raw_email = (post.get("email") or "").strip()
        normalized_email = tools.email_normalize(raw_email)
        organization_raw = post.get("organization_id") or ""
        form_data = {
            "full_name": full_name,
            "email": raw_email,
            "organization_id": organization_raw,
        }
        errors = []
        if not available:
            errors.append(message)
        if len(full_name) < 3:
            errors.append("Ingrese sus nombres completos.")
        elif len(full_name) > 150:
            errors.append("Los nombres completos no pueden superar 150 caracteres.")
        if len(raw_email) > 254:
            normalized_email = False
        if not normalized_email:
            errors.append("Ingrese un correo electrónico válido.")
        try:
            organization_id = int(organization_raw)
        except (TypeError, ValueError):
            organization_id = 0
        organization = event.organization_ids.filtered(
            lambda item: item.id == organization_id and item.active
        )[:1]
        if not organization:
            errors.append("Seleccione una empresa válida.")

        organizations = event.organization_ids.filtered("active")
        if errors:
            return request.render(
                "digital_training_certificate.training_registration_page",
                {
                    "event": event,
                    "organizations": organizations,
                    "available": available,
                    "availability_message": message,
                    "errors": errors,
                    "form_data": form_data,
                },
            )

        attendee_model = request.env["digital.training.attendee"].sudo()
        email = normalized_email.lower()
        existing = attendee_model.search(
            [("event_id", "=", event.id), ("email", "=", email)], limit=1
        )
        if existing:
            return request.render(
                "digital_training_certificate.training_registration_success",
                {"event": event, "attendee": False, "already_registered": True},
            )

        try:
            with request.env.cr.savepoint():
                attendee = attendee_model.create(
                    {
                        "event_id": event.id,
                        "full_name": full_name,
                        "email": email,
                        "organization_id": organization.id,
                    }
                )
        except IntegrityError:
            return request.render(
                "digital_training_certificate.training_registration_success",
                {"event": event, "attendee": False, "already_registered": True},
            )

        attendee.action_generate_and_send_certificate()
        return request.render(
            "digital_training_certificate.training_registration_success",
            {"event": event, "attendee": attendee, "already_registered": False},
        )

    @http.route(
        "/capacitacion/certificado/<string:token>/descargar",
        type="http",
        auth="public",
        website=True,
        sitemap=False,
        methods=["GET"],
    )
    def training_certificate_download(self, token, **kwargs):
        attendee = request.env["digital.training.attendee"].sudo().search(
            [("download_token", "=", token)], limit=1
        )
        if not attendee:
            return request.render(
                "digital_training_certificate.registration_unavailable",
                {"message": "El enlace de descarga no es válido."},
            )
        if not attendee.certificate_attachment_id:
            attendee.action_generate_certificate()
        attachment = attendee.certificate_attachment_id.sudo()
        return request.make_response(
            base64.b64decode(attachment.datas or b""),
            headers=[
                ("Content-Type", "application/pdf"),
                ("Content-Disposition", content_disposition(attachment.name)),
                ("Cache-Control", "private, no-store"),
            ],
        )

    @http.route(
        "/capacitacion/evento/<int:event_id>/qr",
        type="http",
        auth="user",
        website=True,
        sitemap=False,
        methods=["GET"],
    )
    def training_event_qr(self, event_id, **kwargs):
        event = request.env["digital.training.event"].browse(event_id).exists()
        event.check_access_rights("read")
        event.check_access_rule("read")
        return request.render(
            "digital_training_certificate.training_event_qr_page", {"event": event}
        )
