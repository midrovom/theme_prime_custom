from odoo import http, _
from odoo.http import request
import json

import base64
import logging

_logger = logging.getLogger(__name__)


class WebsiteHRRecruitmentCustom(http.Controller):

    @http.route("/my/applications", type="http", auth="user", website=True)
    def my_applications(self, **kwargs):
        applications = request.env['hr.applicant'].sudo().search([
            ('portal_user_id', '=', request.env.user.id)
        ])
        values = {
            'applications': applications,
        }
        return request.render("custom_web_candidatos.portal_my_applications", values)

    @http.route("/jobs/continue/<int:applicant_id>", type="http", auth="user", methods=['GET'], website=True, csrf=False)
    def continue_application(self, applicant_id, **kwargs):
        applicant = request.env['hr.applicant'].sudo().browse(applicant_id)
        if not applicant.exists() or applicant.portal_user_id.id != request.env.user.id:
            return request.not_found()

        full_name = applicant.partner_name or ""
        parts = full_name.split()
        lastname_paterno = parts[0] if len(parts) > 0 else ""
        lastname_materno = parts[1] if len(parts) > 1 else ""
        firstname = " ".join(parts[2:]) if len(parts) > 2 else ""

        values = {
            "applicant": applicant,
            "job": applicant.job_id,
            "firstname": firstname,
            "lastname_paterno": lastname_paterno,
            "lastname_materno": lastname_materno,
            "name": full_name,
            "age": applicant.age,
            "email": applicant.email_from,
            "phone": applicant.partner_phone,
            "cellphone": applicant.partner_mobile,
            "address": applicant.address,
            "parish": applicant.parish,
            "birth_country_id": applicant.birth_country_id.id if applicant.birth_country_id else False,
            "vive_con": applicant.vive_con,
            "tipo_vivienda": applicant.tipo_vivienda,
            "num_hijos": applicant.num_hijos,
            "estado_civil": applicant.estado_civil,
            "cedula": applicant.cedula,
            "birthdate": applicant.birthdate,
            "nacionality": applicant.nacionality,
            "document_type": applicant.document_type,
            "provincia_id": applicant.provincia_id.id if applicant.provincia_id else False,
            "dependientes": applicant.dependientes,
            "image_1920": applicant.image_1920,
            "experiencia": applicant.experiencia,
            # Documentos
            "documents": applicant.document_ids,
            # Información médica
            "medical": applicant.medical_ids,
            # Familiares
            "families": applicant.family_ids,
            # Educación
            "educations": json.dumps(applicant.education_ids.read([
                "level_id", "institucion", "fecha_inicio", "year_fin", "titulo",
                "titulo_por_obtener", "institucion_2", "carrera", "horario", "estado", "study_current",
                "country_id", "state_id"
            ])),
            # Experiencia laboral
            "experiences": json.dumps(applicant.experience_job_ids.read([
                "name", "empresa", "fecha_inicio", "year_fin",
                "tiempo_servicio", "telefonos", "ingreso_mensual",
                "motivo_separacion", "jefe_directo", "cargo_jefe_directo",
                "country_id", "state_id"
            ])),
            # Referencias
            "references": applicant.reference_ids,
            # Catálogos para selects
            "country_states": request.env['res.country.state'].sudo().search([], order="name ASC"),
            "countries": request.env['res.country'].sudo().search([], order="name ASC"),
            "document_types": [
                ('cedula', 'Cédula'),
                ('id_extrj', 'Cédula extranjera'),
                ('pasaporte', 'Pasaporte'),
                ('part_naci', 'Partida de Nacimiento'),
            ],
            "months": [
                ("1", "Enero"), ("2", "Febrero"), ("3", "Marzo"), ("4", "Abril"),
                ("5", "Mayo"), ("6", "Junio"), ("7", "Julio"), ("8", "Agosto"),
                ("9", "Septiembre"), ("10", "Octubre"), ("11", "Noviembre"), ("12", "Diciembre"),
            ],
            "years": [i for i in range(1900, 2026)],
            "days": [i for i in range(1, 32)],
            "family_types": [
                ('1', 'Padre'), ('2', 'Madre'), ('3', 'Hermano(a)'),
                ('4', 'Conyugue'), ('5', 'Hijo(a)'),
            ],
        }

        return request.render("formulario_web_hr_candidatos.web_recruitment", values)
