import json
import re
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

        # Validación server-side de los mismos campos familiares que el JS
        # nativo comprueba antes de continuar.
        index = 1
        while post.get(f"famTipo_{index}") is not None:
            fallecido = post.get(f"famFallecido_{index}") == "1"
            no_tiene = bool(post.get(f"famNoTiene_{index}"))
            if not fallecido and not no_tiene:
                for name in (
                    f"famApellidoPaterno_{index}", f"famApellidoMaterno_{index}",
                    f"famPrimerNombre_{index}", f"famTipoDoc_{index}",
                    f"famFecha_{index}", f"famTelefono_{index}",
                    f"famOcupacion_{index}", f"famDepende_{index}",
                    f"famDisc_{index}",
                ):
                    if not (post.get(name) or "").strip():
                        missing.append(name)

                document_type = (post.get(f"famTipoDoc_{index}") or "").strip()
                document_number = (post.get(f"famCedula_{index}") or "").strip()

                if document_type == "part_naci":
                    upload = request.httprequest.files.get(f"famArchivo_{index}")
                    if not upload or not upload.filename:
                        missing.append(f"famArchivo_{index}")
                elif document_type in ("cedula", "id_extrj", "pasaporte"):
                    if not document_number:
                        missing.append(f"famCedula_{index}")
                    elif document_type == "cedula" and not self._is_valid_ecuadorian_id(document_number):
                        missing.append(f"famCedula_{index}")
                    elif document_type == "id_extrj" and not re.fullmatch(r"\d{10}", document_number):
                        missing.append(f"famCedula_{index}")
                else:
                    missing.append(f"famTipoDoc_{index}")
            index += 1
        return missing

    @staticmethod
    def _is_valid_ecuadorian_id(value):
        cedula = re.sub(r"\D", "", str(value or ""))
        if len(cedula) != 10:
            return False
        province = int(cedula[:2])
        if province < 1 or province > 24 or int(cedula[2]) > 5:
            return False
        coefficients = [2, 1, 2, 1, 2, 1, 2, 1, 2]
        total = 0
        for i, coefficient in enumerate(coefficients):
            product = int(cedula[i]) * coefficient
            total += product - 9 if product >= 10 else product
        verifier = (10 - (total % 10)) % 10
        return verifier == int(cedula[9])

    def _medical_values(self, post):
        return {field: (post.get(field) or "").strip() for field in FORM2_MEDICAL_FIELDS}

    def _family_values(self, post):
        values, index = [], 1
        while post.get(f"famTipo_{index}") is not None:
            fallecido = post.get(f"famFallecido_{index}") == "1"
            no_tiene = bool(post.get(f"famNoTiene_{index}"))
            name = (post.get(f"famNombre_{index}") or "").strip()
            if fallecido:
                name = "FALLECIDO"
            elif no_tiene:
                name = "NO TIENE"

            file_value = False
            file_name = False
            try:
                uploaded = request.httprequest.files.get(f"famArchivo_{index}")
                if uploaded and uploaded.filename:
                    import base64
                    file_value = base64.b64encode(uploaded.read())
                    file_name = uploaded.filename
            except Exception:
                pass

            values.append({
                "name": name,
                "familiar_type": post.get(f"famTipo_{index}") or False,
                "fallecido": fallecido,
                "no_tiene": no_tiene,
                "document_type": False if fallecido else (post.get(f"famTipoDoc_{index}") or False),
                "cedula": "" if fallecido else (post.get(f"famCedula_{index}") or "").strip(),
                "birthdate": False if fallecido else (post.get(f"famFecha_{index}") or False),
                "phone": "" if fallecido else (post.get(f"famTelefono_{index}") or "").strip(),
                "occupation": "" if fallecido else (post.get(f"famOcupacion_{index}") or "").strip(),
                "economically_dependent": False if fallecido else (post.get(f"famDepende_{index}") or False),
                "disability": False if fallecido else (post.get(f"famDisc_{index}") or False),
                "disability_type": "" if fallecido else (post.get(f"famDiscTipo_{index}") or "").strip(),
                "disability_percentage": int(post.get(f"famDiscPorcentaje_{index}") or 0),
                "filename": file_name,
                "document_file": file_value,
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
        # Formulario 2 es de un solo envío: una vez completado, no se
        # permite volver a abrirlo ni sobrescribir sus datos desde el portal.
        if not applicant._portal_can_continue_form2(request.env.user):
            raise Forbidden()

        missing = self._validate_form2(post)
        if missing:
            return request.render(
                "hr_applications_portal_ext.application_form_2_page",
                dict(
                    {"application": applicant,
                     "error": "Complete los campos obligatorios del Formulario 2 antes de guardar.",
                     "missing_fields": missing, "post": post},
                    **self._form2_payload(applicant),
                ),
                status=400,
            )

        medical = applicant.sudo().medical_ids[:1]
        values = self._medical_values(post)
        if medical:
            medical.sudo().write(values)
        else:
            request.env["applicant.medical"].sudo().create(dict(values, applicant_id=applicant.id))

        family_values = self._family_values(post)
        applicant.sudo().family_ids.unlink()
        if family_values:
            request.env["applicant.family"].sudo().create(
                [dict(vals, applicant_id=applicant.id) for vals in family_values]
            )

        applicant._complete_phase_2()
        return request.redirect("/my/applications?form2_saved=1")
