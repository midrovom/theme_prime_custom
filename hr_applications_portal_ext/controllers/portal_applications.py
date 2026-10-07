import json
from datetime import date, datetime

from odoo import http
from odoo.http import request
from werkzeug.exceptions import NotFound, Forbidden

FORM2_MEDICAL_FIELDS = (
    "enfermedad_persistente", "detalle_enfermedad_persistente",
    "medicacion_continua", "detalle_medicacion_continua",
    "enfermedad_laboral", "detalle_enfermedad_laboral",
    "cirugia_realizada", "detalle_cirugia_realizada",
    "discapacidad", "tipo_discapacidad",
    "porcentaje_discapacidad", "tipo_sangre",
)

class HrApplicationsPortal(http.Controller):

    def _portal_user(self):
        user = request.env.user
        if user._is_public() or not user.has_group("base.group_portal"):
            raise Forbidden()
        return user

    def _get_owned_application(self, application_id):
        user = self._portal_user()
        applicant = request.env["hr.applicant"].search([
            ("id", "=", application_id),
            ("portal_user_id", "=", user.id),
        ], limit=1)
        if not applicant:
            raise NotFound()
        if applicant.portal_user_id.id != user.id:
            raise Forbidden()
        return applicant

    def _validate_form2(self, post):
        required = (
            "enfermedad_persistente", "medicacion_continua",
            "enfermedad_laboral", "cirugia_realizada",
            "discapacidad", "tipo_sangre",
        )
        missing = [name for name in required if not (post.get(name) or "").strip()]
        for choice, detail in (
            ("enfermedad_persistente", "detalle_enfermedad_persistente"),
            ("medicacion_continua", "detalle_medicacion_continua"),
            ("enfermedad_laboral", "detalle_enfermedad_laboral"),
            ("cirugia_realizada", "detalle_cirugia_realizada"),
        ):
            if post.get(choice) == "si" and not (post.get(detail) or "").strip():
                missing.append(detail)
        if post.get("discapacidad") == "si":
            for name in ("tipo_discapacidad", "porcentaje_discapacidad"):
                if not (post.get(name) or "").strip():
                    missing.append(name)
        return missing

    def _medical_values(self, post):
        return {field: (post.get(field) or "").strip() for field in FORM2_MEDICAL_FIELDS}

    def _family_values(self, post):
        values, index = [], 1
        while post.get(f"famNombre_{index}") is not None:
            name = (post.get(f"famNombre_{index}") or "").strip()
            if name:
                values.append({
                    "name": name,
                    "cedula": (post.get(f"famCedula_{index}") or "").strip(),
                    "birthdate": post.get(f"famFecha_{index}") or False,
                    "phone": (post.get(f"famTelefono_{index}") or "").strip(),
                    "occupation": (post.get(f"famOcupacion_{index}") or "").strip(),
                    "economically_dependent": post.get(f"famDepende_{index}") or False,
                    "disability": post.get(f"famDisc_{index}") or False,
                    "disability_type": (post.get(f"famDiscTipo_{index}") or "").strip(),
                })
            index += 1
        return values

    @staticmethod
    def _json_default(value):
        if isinstance(value, (date, datetime)):
            return value.isoformat()
        return str(value)

    def _form2_payload(self, applicant):
        medical = applicant.medical_ids[:1].read()[0] if applicant.medical_ids else {}
        families = applicant.family_ids.read() if applicant.family_ids else []
        return {
            "medical_json": json.dumps(medical, default=self._json_default),
            "families_json": json.dumps(families, default=self._json_default),
            "num_hijos": applicant.num_hijos or 0,
        }

    @http.route("/my/applications", type="http", auth="user", website=True, methods=["GET"])
    def my_applications(self, **kwargs):
        user = self._portal_user()
        applications = request.env["hr.applicant"].search(
            [("portal_user_id", "=", user.id)],
            order="create_date desc, id desc",
        )
        return request.render("hr_applications_portal_ext.portal_my_applications",
                              {"applications": applications})

    @http.route("/my/applications/<int:application_id>/form2",
                type="http", auth="user", website=True, methods=["GET"])
    def application_form2(self, application_id, **kwargs):
        applicant = self._get_owned_application(application_id)
        if not applicant._portal_can_continue_form2(request.env.user):
            raise Forbidden()
        values = {"application": applicant}
        values.update(self._form2_payload(applicant))
        return request.render(
            "hr_applications_portal_ext.application_form_2_page", values
        )

    @http.route("/my/applications/<int:application_id>/form2/save",
                type="http", auth="user", website=True, methods=["POST"], csrf=True)
    def application_form2_save(self, application_id, **post):
        applicant = self._get_owned_application(application_id)
        if applicant.portal_user_id.id != request.env.user.id:
            raise Forbidden()

        missing = self._validate_form2(post)
        if missing:
            return request.render(
                "hr_applications_portal_ext.application_form_2_page",
                dict(
                    {"application": applicant,
                     "error": "Complete los campos obligatorios de salud antes de guardar.",
                     "missing_fields": missing, "post": post},
                    **self._form2_payload(applicant),
                ),
                status=400,
            )

        medical = applicant.medical_ids[:1]
        values = self._medical_values(post)
        if medical:
            medical.write(values)
        else:
            request.env["applicant.medical"].create(dict(values, applicant_id=applicant.id))

        family_values = self._family_values(post)
        applicant.family_ids.unlink()
        if family_values:
            request.env["applicant.family"].create(
                [dict(vals, applicant_id=applicant.id) for vals in family_values]
            )

        applicant._complete_phase_2()
        return request.redirect("/my/applications?form2_saved=1")
