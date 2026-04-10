from odoo import http, _
from odoo.http import request
from werkzeug.exceptions import BadRequest
from werkzeug.utils import secure_filename

import base64
import logging

_logger = logging.getLogger(__name__)

DAYS = [ i for i in range(1,32) ]
MONTHS = [
    ("1", "Enero"),
    ('2', 'Febrero'),
    ('3', 'Marzo'),
    ('4', 'Abril'),
    ('5', 'Mayo'),
    ('6', 'Junio'),
    ('7', 'Julio'),
    ('8', 'Agosto'),
    ('9', 'Septiembre'),
    ('10', 'Octubre'),
    ('11', 'Noviembre'),
    ('12', 'Diciembre'),
]
YEARS = [ i for i in range(1900, 2026) ]

DOCUMENT_TYPES = [
    ('cedula', 'Cedula'),
    ('ruc', 'RUC'),
    ('pasaporte', 'Pasaporte'),
]

class WebsiteHRRecruitment(http.Controller):

    @http.route('''/jobs/recruitment/<model("hr.job"):job>''', type="http", auth="public", website=True, sitemap=True)
    def recruitment(self, job, **kwargs):
        values = {
            "job": job,
            "country_states": request.env['res.country.state'].sudo().search([], order="name ASC"),
            "countries": request.env['res.country'].sudo().search([], order="name ASC"),
            "document_types": DOCUMENT_TYPES,
            "months": MONTHS,
            "years": YEARS,
            "days": DAYS,
        }
        return request.render("custom_web_hr_datos_candidatos.web_recruitment", values)

    @http.route("/jobs/submit", type="http", auth="public", methods=['POST'], website=True, csrf=False)
    def submit_form(self, **kwargs):

        def safe_int(value):
            try:
                return int(value) if value not in (None, '', False) else 0
            except:
                return 0

        try:
            _logger.info(f"VALUES >>> {kwargs}")

            # Recuperar archivo del formulario
            imagen_file = request.httprequest.files.get('imagen')
            imagen_b64 = False
            if imagen_file:
                imagen_b64 = base64.b64encode(imagen_file.read())

            dependientes_list = request.httprequest.form.getlist('dependientes')
            dependientes = ', '.join(dependientes_list) if dependientes_list else ''

            # Crear Candidate con los campos separados
            candidate_vals = {
                'firstname': kwargs.get('firstname'),
                'lastname_paterno': kwargs.get('lastname_paterno'),
                'lastname_materno': kwargs.get('lastname_materno'),
            }
            candidate = request.env['hr.candidate'].sudo().create(candidate_vals)

            # Crear Applicant relacionado con Candidate
            applicant_values = {
                'job_id': safe_int(kwargs.get('jobId')),
                #'name': f"{candidate.name} - {kwargs.get('jobName')}",  # usa el nombre completo computado del Candidate
                'partner_name': candidate.name,
                'candidate_id': candidate.id,
                'dependientes': dependientes,
                'age': safe_int(kwargs.get('age')),
                'email_from': kwargs.get('email'),
                'partner_phone': f"{kwargs.get('codePhone') or ''}{kwargs.get('phone') or ''}",
                'partner_mobile': f"{kwargs.get('codeCellphone') or ''}{kwargs.get('cellphone') or ''}",
                'address': kwargs.get('address'),
                'parish': kwargs.get('parish'),
                'birth_country_id': safe_int(kwargs.get('birthCountry')),
                'vive_con': kwargs.get('viveCon'),
                'tipo_vivienda': kwargs.get('tipoVivienda'),
                'num_hijos': safe_int(kwargs.get('numHijos')),
                'estado_civil': kwargs.get('estadoCivil'),
                'secondary_studies': kwargs.get('studyOptions') == 't',
                'disability': kwargs.get('jobOptions') == 't',
                'family_disability': kwargs.get('discOptions') == 't',
                'cedula': kwargs.get('documentNumber'),
                'birthdate': f"{kwargs.get('anioNacimiento')}-{kwargs.get('mesNacimiento')}-{kwargs.get('diaNacimiento')}",
                'nacionality': kwargs.get('nationality'),
                'document_type': kwargs.get('documentType'),
                'provincia_id': safe_int(kwargs.get('provincia')),
                'image_1920': imagen_b64,
            }

            # ---------------- Información Médica ----------------
            medical_lines = [(0, 0, {
                'enfermedad_persistente': kwargs.get('enfermedad_persistente') or 'no',
                'detalle_enfermedad_persistente': kwargs.get('detalle_enfermedad_persistente') or '',
                'medicacion_continua': kwargs.get('medicacion_continua') or 'no',
                'detalle_medicacion_continua': kwargs.get('detalle_medicacion_continua') or '',
                'enfermedad_laboral': kwargs.get('enfermedad_laboral') or 'no',
                'detalle_enfermedad_laboral': kwargs.get('detalle_enfermedad_laboral') or '',
                'cirugia_realizada': kwargs.get('cirugia_realizada') or 'no',
                'detalle_cirugia_realizada': kwargs.get('detalle_cirugia_realizada') or '',
                'discapacidad': kwargs.get('discapacidad') or 'no',
                'tipo_discapacidad': kwargs.get('tipo_discapacidad') or '',
                'porcentaje_discapacidad': kwargs.get('porcentaje_discapacidad') or '',
                'tipo_sangre': kwargs.get('tipo_sangre') or '',
            })]

            applicant_values['medical_ids'] = medical_lines

            # ---------------- Familiares ----------------

            family_lines = []
            k = 1

            while kwargs.get(f'famNombre_{k}') is not None:

                name = kwargs.get(f'famNombre_{k}')

                if name:
                    family_lines.append((0, 0, {
                        'name': name,
                        'cedula': kwargs.get(f'famCedula_{k}'),
                        'birthdate': kwargs.get(f'famFecha_{k}'),
                        'phone': kwargs.get(f'famTelefono_{k}'),
                        'occupation': kwargs.get(f'famOcupacion_{k}'),
                        'economically_dependent': kwargs.get(f'famDepende_{k}'),
                        'disability': kwargs.get(f'famDisc_{k}'),
                        'disability_type': kwargs.get(f'famDiscTipo_{k}'),
                    }))

                k += 1

            if family_lines:
                applicant_values['family_ids'] = family_lines

            # ---------------- Funcion para parseo de localizacion Pais/Ciudad ----------------
            # def parse_location(val):
            #     if not val:
            #         return None
            #     val = str(val)
            #     if val.startswith("country-"):
            #         return f"res.country,{val[8:]}"
            #     if val.startswith("state-"):
            #         return f"res.country.state,{val[6:]}"
            #     return None

            def parse_location(val):
                if not val:
                    return None
                val = str(val)
                if val.startswith("country-"):
                    country = request.env['res.country'].sudo().browse(int(val[8:]))
                    return country.name if country else None
                if val.startswith("state-"):
                    state = request.env['res.country.state'].sudo().browse(int(val[6:]))
                    return state.name if state else None
                return None

            # ---------------- Formación Académica ----------------
            education_lines = []
            i = 1

            while kwargs.get(f'titulo_{i}') is not None:
                titulo = kwargs.get(f'titulo_{i}')
                level_id = safe_int(kwargs.get(f'level_id_{i}'))

                if titulo and level_id:
                    education_lines.append((0, 0, {
                        'level_id': level_id,
                        'location_name': parse_location(kwargs.get(f'paisEducacion_{i}')),
                        'titulo': titulo,
                        'fecha_inicio': kwargs.get(f'inicioEstudio_{i}'),
                        'year_fin': kwargs.get(f'finEstudio_{i}'),
                        'institucion': kwargs.get(f'institucion_{i}'),
                        'titulo_por_obtener': kwargs.get('titulo_por_obtener') or '',
                        'institucion_2': kwargs.get(f'institucion_2_{i}') or '',   
                        'nivel_actual': kwargs.get(f'estado_{i}') or '',         
                        'horario': kwargs.get('horario') or '',
                        'carrera': kwargs.get('carrera') or '',
                        'estado': kwargs.get('estado') or '',
                        'study_current': 'si' if kwargs.get('studyOptions') == 't' else 'no',
                    }))
                i += 1

            if education_lines:
                applicant_values['education_ids'] = education_lines


            # ---------------- Experiencia Laboral ----------------
            experience_lines = []
            j = 1

            while kwargs.get(f'cargo_{j}') is not None:
                cargo = kwargs.get(f'cargo_{j}')

                if cargo:
                    experience_lines.append((0, 0, {
                        'name': cargo,
                        'empresa': kwargs.get(f'company_{j}'),
                        'location_name': parse_location(kwargs.get(f'paisExperiencia_{j}')),
                        'fecha_inicio': kwargs.get(f'jobInicio_{j}'),
                        'year_fin': kwargs.get(f'jobFin_{j}'),
                        'tiempo_servicio': kwargs.get(f'tiempo_{j}'),
                        'telefonos': kwargs.get(f'telefonos_{j}'),
                        'ingreso_mensual': kwargs.get(f'ingreso_{j}'),
                        'motivo_separacion': kwargs.get(f'motivo_{j}'),
                        'jefe_directo': kwargs.get(f'jefe_{j}'),
                        'cargo_jefe_directo': kwargs.get(f'cargoJefe_{j}'),
                    }))
                j += 1

            if experience_lines:
                applicant_values['experience_job_ids'] = experience_lines

            # ---------------- Familiares o conocidos del grupo ----------------

            known_lines = []

            nombre = kwargs.get('knownNombre_1')
            posee = kwargs.get('knownPosee_1')
            relacion = kwargs.get('knownRelacion_1')
            parentesco = kwargs.get('knownParentesco_1')

            if nombre or posee or relacion:
                posee = 'si' if posee == 't' else 'no'

                if relacion not in ['familiar', 'amigo', 'conocido']:
                    relacion = False

                if relacion != 'familiar':
                    parentesco = False

                known_lines.append((0, 0, {
                    'posee_familiares': posee,
                    'nombre_completo': nombre,
                    'relacion': relacion,
                    'parentesco': parentesco,
                }))

            if known_lines:
                applicant_values['known_ids'] = known_lines

            # ---------------- Referencias personales ----------------

            reference_lines = []
            m = 1

            while kwargs.get(f'ref_nombre_{m}') is not None:

                nombre = kwargs.get(f'ref_nombre_{m}')

                if nombre:
                    reference_lines.append((0, 0, {
                        'nombre': nombre,
                        'domicilio': kwargs.get(f'ref_domicilio_{m}'),
                        'telefono': kwargs.get(f'ref_telefono_{m}'),
                        'ocupacion': kwargs.get(f'ref_ocupacion_{m}'),
                        'tiempo_conocerlo': kwargs.get(f'ref_tiempo_{m}'),
                    }))

                m += 1

            if reference_lines:
                applicant_values['reference_ids'] = reference_lines


            # ---------------- Crear postulante ----------------

            applicant = request.env['hr.applicant'].sudo().create(applicant_values)

            # ---------------- Adjuntar archivos ----------------

            files = request.httprequest.files
            for field_name, file_storage in files.items():
                if not file_storage.filename:
                    continue
                file_content = file_storage.read()
                if not file_content:
                    continue
                request.env['ir.attachment'].sudo().create({
                    'name': secure_filename(file_storage.filename),
                    'type': 'binary',
                    'datas': base64.b64encode(file_content),
                    'res_model': 'hr.applicant',
                    'res_id': applicant.id,
                    'mimetype': file_storage.content_type,
                })

        except Exception:
            _logger.exception('ERROR FORM COMPLETO')
            raise

        return request.redirect('/job-thank-you')
