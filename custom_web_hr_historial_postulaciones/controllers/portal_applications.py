import base64
import json
import logging
import re

from werkzeug.exceptions import Forbidden, NotFound
from werkzeug.utils import secure_filename

from odoo import fields, http, _
from odoo.http import request
from odoo.addons.http_routing.models.ir_http import slug
from odoo.exceptions import ValidationError


_logger = logging.getLogger(__name__)

DAYS = list(range(1, 32))
MONTHS = [
    ('1', 'Enero'), ('2', 'Febrero'), ('3', 'Marzo'), ('4', 'Abril'),
    ('5', 'Mayo'), ('6', 'Junio'), ('7', 'Julio'), ('8', 'Agosto'),
    ('9', 'Septiembre'), ('10', 'Octubre'), ('11', 'Noviembre'), ('12', 'Diciembre'),
]
YEARS = list(range(1900, 2027))

DOCUMENT_FIELDS = [
    ('fotografia', 'Fotografía actualizada a color tamaño carnet', ('pdf', 'jpg', 'jpeg', 'png')),
    ('cedula_votacion', '2 copias a color de cédula de identidad y certificado de votación', ('pdf',)),
    ('historia_iess', 'Historia laboral extraída de la página web del IESS', ('pdf',)),
    ('acta_matrimonio', 'Acta de matrimonio / unión de hecho', ('pdf',)),
    ('documentos_hijos', 'Documentos de hijos menores de 18 años', ('pdf',)),
    ('estudios_titulo', 'Certificado de estudios / título certificado por SENESCYT', ('pdf',)),
    ('cursos_realizados', 'Cursos realizados', ('pdf',)),
    ('recomendaciones', 'Recomendaciones originales y actualizadas (mínimo 2)', ('pdf',)),
    ('certificados_trabajo', 'Certificados de trabajos anteriores', ('pdf',)),
    ('planilla_servicios', 'Planilla de servicios básicos actualizada', ('pdf',)),
    ('croquis_domicilio', 'Croquis del domicilio', ('pdf',)),
    ('formulario_107', 'Formulario No. 107 del SRI', ('pdf',)),
    ('cuenta_banco_internacional', 'Cuenta de ahorros Banco Internacional', ('pdf',)),
    ('certificado_salud', 'Certificado de salud MSP con tipo de sangre', ('pdf',)),
]


def _safe_int(value):
    try:
        return int(value) if value not in (None, '', False) else 0
    except (TypeError, ValueError):
        return 0


def _clean(value):
    if value in (None, False):
        return ''
    return str(value).strip()


def _split_phone(value):
    value = _clean(value)
    if not value:
        return '+593', ''
    match = re.match(r'^(\+\d{1,3})(.*)$', value)
    if match:
        return match.group(1), match.group(2).strip()
    return '+593', value


def _b64_file(file_storage):
    if not file_storage or not getattr(file_storage, 'filename', None):
        return False, False
    content = file_storage.read()
    if not content:
        return False, False
    return base64.b64encode(content).decode('ascii'), secure_filename(file_storage.filename)


class PortalApplications(http.Controller):

    def _get_owned_applicant(self, applicant_id, sudo=True):
        env = request.env['hr.applicant'].sudo() if sudo else request.env['hr.applicant']
        applicant = env.browse(applicant_id).exists()
        if not applicant or applicant.portal_user_id.id != request.env.user.id:
            raise NotFound()
        return applicant

    def _documentation_enabled(self, applicant):
        return bool(applicant.stage_id and applicant.stage_id.sequence >= 3)

    def _portal_context(self):
        user = request.env.user
        applicants = request.env['hr.applicant'].sudo().search(
            [('portal_user_id', '=', user.id)],
            order='create_date desc, id desc',
        )
        return applicants

    def _common_form_values(self, applicant=None):
        countries = request.env['res.country'].sudo().search([], order='name ASC')
        states = request.env['res.country.state'].sudo().search([], order='name ASC')
        document_types = [
            ('cedula', 'Cédula'),
            ('id_extrj', 'Cédula extranjera'),
            ('pasaporte', 'Pasaporte'),
            ('part_naci', 'Partida de Nacimiento'),
        ]
        family_types = [
            ('1', 'Padre'), ('2', 'Madre'), ('3', 'Hermano(a)'),
            ('4', 'Conyugue'), ('5', 'Hijo(a)'),
        ]
        return {
            'job': applicant.job_id if applicant else False,
            'country_states': states,
            'countries': countries,
            'document_types': document_types,
            'days': DAYS,
            'months': MONTHS,
            'years': YEARS,
            'family_types': family_types,
            'applicant': applicant,
        }

    @http.route('/my/application-history', type='http', auth='user', website=True)
    def application_history(self, **kwargs):
        applicants = self._portal_context()
        return request.render(
            'custom_web_hr_historial_postulaciones.portal_application_history',
            {'applicants': applicants},
        )

    @http.route('/my/application-documentation', type='http', auth='user', website=True)
    def documentation_index(self, **kwargs):
        applicants = self._portal_context().filtered(self._documentation_enabled)
        return request.render(
            'custom_web_hr_historial_postulaciones.portal_documentation_index',
            {'applicants': applicants},
        )

    @http.route('/my/application/<int:applicant_id>/edit', type='http', auth='user', website=True)
    def edit_application(self, applicant_id, **kwargs):
        applicant = self._get_owned_applicant(applicant_id)
        if not applicant.portal_update_allowed:
            raise Forbidden(_('Esta postulación no está habilitada para actualización.'))

        # Abrimos el mismo formulario nativo que se utiliza para una nueva postulación.
        # El parámetro edit_applicant permite que el JS del módulo cargue los datos
        # existentes y cambie únicamente el destino del envío al endpoint de actualización.
        if not applicant.job_id:
            raise NotFound(_('La postulación no tiene un puesto asociado.'))

        return request.redirect(
            '/jobs/recruitment/%s?edit_applicant=%s' % (slug(applicant.job_id), applicant.id)
        )

    @http.route('/my/application/<int:applicant_id>/data', type='http', auth='user', website=True, methods=['GET'], csrf=False)
    def application_data(self, applicant_id, **kwargs):
        applicant = self._get_owned_applicant(applicant_id)
        birthdate = applicant.birthdate
        day = birthdate.day if birthdate else ''
        month = birthdate.month if birthdate else ''
        year = birthdate.year if birthdate else ''
        code_cell, cellphone = _split_phone(applicant.partner_mobile)
        code_phone, phone = _split_phone(applicant.partner_phone)
        medical = applicant.medical_ids[:1]
        medical_values = {
            field: medical[field] if medical else ''
            for field in [
                'enfermedad_persistente', 'detalle_enfermedad_persistente',
                'medicacion_continua', 'detalle_medicacion_continua',
                'enfermedad_laboral', 'detalle_enfermedad_laboral',
                'cirugia_realizada', 'detalle_cirugia_realizada',
                'discapacidad', 'tipo_discapacidad', 'porcentaje_discapacidad',
                'tipo_sangre',
            ]
        }

        payload = {
            'id': applicant.id,
            'job_id': applicant.job_id.id,
            'has_image': bool(applicant.image_1920),
            'has_curriculum': bool(applicant.document_ids),
            'firstname': applicant.candidate_id.firstname if applicant.candidate_id else '',
            'lastname_paterno': applicant.candidate_id.lastname_paterno if applicant.candidate_id else '',
            'lastname_materno': applicant.candidate_id.lastname_materno if applicant.candidate_id else '',
            'age': applicant.age or '',
            'address': applicant.address or '',
            'parish': applicant.parish or '',
            'birth_country_id': applicant.birth_country_id.id if applicant.birth_country_id else '',
            'provincia_id': applicant.provincia_id.id if applicant.provincia_id else '',
            'birthdate': {'day': day, 'month': month, 'year': year},
            'phone_code': code_phone,
            'phone': phone,
            'cellphone_code': code_cell,
            'cellphone': cellphone,
            'vive_con': applicant.vive_con or '',
            'tipo_vivienda': applicant.tipo_vivienda or '',
            'num_hijos': applicant.num_hijos or 0,
            'dependientes': [x.strip() for x in (applicant.dependientes or '').split(',') if x.strip()],
            'email': applicant.email_from or request.env.user.email or '',
            'document_type': applicant.document_type or '',
            'document_number': applicant.cedula or '',
            'nationality': applicant.nacionality or '',
            'estado_civil': applicant.estado_civil or '',
            'secondary_studies': bool(applicant.secondary_studies),
            'disability': bool(applicant.disability),
            'family_disability': bool(applicant.family_disability),
            'medical': medical_values,
            'family': [
                {
                    'familiar_type': family.familiar_type or '',
                    'name': family.name or '',
                    'fallecido': family.fallecido,
                    'no_tiene': family.no_tiene,
                    'document_type': family.document_type or '',
                    'cedula': family.cedula or '',
                    'birthdate': str(family.birthdate) if family.birthdate else '',
                    'phone': family.phone or '',
                    'occupation': family.occupation or '',
                    'economically_dependent': family.economically_dependent or '',
                    'disability': family.disability or '',
                    'disability_type': family.disability_type or '',
                    'disability_percentage': family.disability_percentage or '',
                }
                for family in applicant.family_ids.sorted(key=lambda r: (r.familiar_type or '', r.id))
            ],
            'education': [
                {
                    'level_id': education.level_id.id if education.level_id else '',
                    'institucion': education.institucion or '',
                    'fecha_inicio': str(education.fecha_inicio) if education.fecha_inicio else '',
                    'year_fin': education.year_fin or '',
                    'country_id': education.country_id.id if education.country_id else '',
                    'state_id': education.state_id.id if education.state_id else '',
                    'titulo': education.titulo or '',
                    'titulo_por_obtener': education.titulo_por_obtener or '',
                    'institucion_2': education.institucion_2 or '',
                    'horario': education.horario or '',
                    'carrera': education.carrera or '',
                    'estado': education.estado or '',
                    'study_current': education.study_current or '',
                }
                for education in applicant.education_ids.sorted('id')
            ],
            'experience': [
                {
                    'name': exp.name or '',
                    'empresa': exp.empresa or '',
                    'country_id': exp.country_id.id if exp.country_id else '',
                    'state_id': exp.state_id.id if exp.state_id else '',
                    'fecha_inicio': str(exp.fecha_inicio) if exp.fecha_inicio else '',
                    'year_fin': exp.year_fin or '',
                    'tiempo_servicio': exp.tiempo_servicio or '',
                    'telefonos': exp.telefonos or '',
                    'ingreso_mensual': exp.ingreso_mensual or 0,
                    'motivo_separacion': exp.motivo_separacion or '',
                    'jefe_directo': exp.jefe_directo or '',
                    'cargo_jefe_directo': exp.cargo_jefe_directo or '',
                }
                for exp in applicant.experience_job_ids.sorted('id')
            ],
            'known': {
                'posee': (applicant.known_ids[:1].posee_familiares == 'si') if applicant.known_ids else False,
                'nombre': applicant.known_ids[:1].nombre_completo if applicant.known_ids else '',
                'relacion': applicant.known_ids[:1].relacion if applicant.known_ids else '',
                'parentesco': applicant.known_ids[:1].parentesco if applicant.known_ids else '',
            },
            'references': [
                {
                    'nombre': ref.nombre or '',
                    'domicilio': ref.domicilio or '',
                    'telefono': ref.telefono or '',
                    'ocupacion': ref.ocupacion or '',
                    'tiempo_conocerlo': ref.tiempo_conocerlo or '',
                }
                for ref in applicant.reference_ids.sorted('id')
            ],
        }
        return request.make_response(
            json.dumps(payload, default=str),
            headers=[('Content-Type', 'application/json; charset=utf-8')],
        )

    def _parse_applicant_values(self, kwargs, applicant=None):
        dependientes_list = request.httprequest.form.getlist('dependientes')
        dependientes = ', '.join(dependientes_list) if dependientes_list else ''
        birth_day = _clean(kwargs.get('diaNacimiento'))
        birth_month = _clean(kwargs.get('mesNacimiento'))
        birth_year = _clean(kwargs.get('anioNacimiento'))
        birthdate = False
        if birth_day.isdigit() and birth_month.isdigit() and birth_year.isdigit():
            birthdate = f'{int(birth_year):04d}-{int(birth_month):02d}-{int(birth_day):02d}'

        image_file = request.httprequest.files.get('imagen')
        image_b64 = False
        if image_file and image_file.filename:
            content = image_file.read()
            if content:
                image_b64 = base64.b64encode(content)

        code_phone = _clean(kwargs.get('codePhone'))
        code_cellphone = _clean(kwargs.get('codeCellphone'))
        phone = _clean(kwargs.get('phone'))
        cellphone = _clean(kwargs.get('cellphone'))

        values = {
            'job_id': _safe_int(kwargs.get('jobId')),
            'partner_name': _clean(kwargs.get('lastname_paterno')) + ' ' + _clean(kwargs.get('lastname_materno')) + ' ' + _clean(kwargs.get('firstname')),
            'dependientes': dependientes,
            'age': _safe_int(kwargs.get('age')),
            'email_from': kwargs.get('email'),
            'partner_phone': f'{code_phone}{phone}',
            'partner_mobile': f'{code_cellphone}{cellphone}',
            'address': kwargs.get('address'),
            'parish': kwargs.get('parish'),
            'birth_country_id': _safe_int(kwargs.get('birthCountry')),
            'vive_con': kwargs.get('viveCon'),
            'tipo_vivienda': kwargs.get('tipoVivienda'),
            'num_hijos': _safe_int(kwargs.get('numHijos')),
            'estado_civil': kwargs.get('estadoCivil'),
            'secondary_studies': kwargs.get('studyOptions') == 't',
            'disability': kwargs.get('jobOptions') == 't',
            'family_disability': kwargs.get('discOptions') == 't',
            'cedula': kwargs.get('documentNumber'),
            'birthdate': birthdate,
            'nacionality': kwargs.get('nationality'),
            'document_type': kwargs.get('documentType'),
            'provincia_id': _safe_int(kwargs.get('provincia')),
            'experiencia': _safe_int(kwargs.get('total_experiences')),
        }
        if image_b64:
            values['image_1920'] = image_b64
        elif applicant:
            values['image_1920'] = applicant.image_1920
        return values

    def _build_child_commands(self, kwargs):
        family_lines = []
        k = 1
        while kwargs.get(f'famTipo_{k}') is not None:
            tipo = kwargs.get(f'famTipo_{k}')
            fallecido = kwargs.get(f'famFallecido_{k}') == '1'
            no_tiene = bool(kwargs.get(f'famNoTiene_{k}'))
            name = kwargs.get(f'famNombre_{k}') or False
            if fallecido:
                name = 'FALLECIDO'
            elif no_tiene:
                name = 'NO TIENE'
            family_lines.append((0, 0, {
                'name': name,
                'familiar_type': str(tipo) if tipo else False,
                'fallecido': fallecido,
                'no_tiene': no_tiene,
                'document_type': False if fallecido else kwargs.get(f'famTipoDoc_{k}'),
                'birthdate': False if fallecido else kwargs.get(f'famFecha_{k}'),
                'phone': False if fallecido else kwargs.get(f'famTelefono_{k}'),
                'occupation': False if fallecido else kwargs.get(f'famOcupacion_{k}'),
                'economically_dependent': False if fallecido else kwargs.get(f'famDepende_{k}'),
                'disability': False if fallecido else kwargs.get(f'famDisc_{k}'),
                'disability_type': False if fallecido else kwargs.get(f'famDiscTipo_{k}'),
                'disability_percentage': False if fallecido else kwargs.get(f'famDiscPorcentaje_{k}'),
                'cedula': False if fallecido else kwargs.get(f'famCedula_{k}'),
                'filename': False,
                'document_file': False,
            }))
            k += 1

        education_lines = []
        i = 1
        while kwargs.get(f'titulo_{i}') is not None:
            titulo = kwargs.get(f'titulo_{i}')
            level_id = _safe_int(kwargs.get(f'level_id_{i}'))
            if titulo and level_id:
                education_lines.append((0, 0, {
                    'level_id': level_id,
                    'country_id': _safe_int(kwargs.get(f'paisEducacion_{i}')) if str(kwargs.get(f'paisEducacion_{i}') or '').isdigit() else _safe_int(str(kwargs.get(f'paisEducacion_{i}') or '').replace('country-', '')),
                    'state_id': _safe_int(str(kwargs.get(f'ciudad_{i}') or '').replace('state-', '')),
                    'titulo': titulo,
                    'fecha_inicio': kwargs.get(f'inicioEstudio_{i}'),
                    'year_fin': kwargs.get(f'finEstudio_{i}'),
                    'institucion': kwargs.get(f'institucion_{i}'),
                    'titulo_por_obtener': kwargs.get('titulo_por_obtener') or '',
                    'institucion_2': kwargs.get('institucion_2') or '',
                    'horario': kwargs.get('horario') or '',
                    'carrera': kwargs.get('carrera') or '',
                    'estado': kwargs.get('estado') or '',
                    'study_current': 'si' if kwargs.get('studyOptions') == 't' else 'no',
                }))
            i += 1

        experience_lines = []
        j = 1
        while kwargs.get(f'cargo_{j}') is not None:
            cargo = kwargs.get(f'cargo_{j}')
            if cargo:
                experience_lines.append((0, 0, {
                    'name': cargo,
                    'empresa': kwargs.get(f'company_{j}'),
                    'country_id': _safe_int(str(kwargs.get(f'paisExperiencia_{j}') or '').replace('country-', '')),
                    'state_id': _safe_int(str(kwargs.get(f'ciudadExperiencia_{j}') or '').replace('state-', '')),
                    'fecha_inicio': kwargs.get(f'jobInicio_{j}'),
                    'year_fin': kwargs.get(f'jobFin_{j}'),
                    'tiempo_servicio': kwargs.get(f'tiempo_{j}'),
                    'telefonos': kwargs.get(f'telefonos_{j}'),
                    'ingreso_mensual': float(kwargs.get(f'ingreso_{j}') or 0),
                    'motivo_separacion': kwargs.get(f'motivo_{j}'),
                    'jefe_directo': kwargs.get(f'jefe_{j}'),
                    'cargo_jefe_directo': kwargs.get(f'cargoJefe_{j}'),
                }))
            j += 1

        reference_lines = []
        m = 0
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

        nombre = kwargs.get('knownNombre_1')
        posee = kwargs.get('knownPosee_1')
        relacion = kwargs.get('knownRelacion_1')
        parentesco = kwargs.get('knownParentesco_1')
        known_lines = []
        if nombre or posee or relacion:
            if relacion not in ['familiar', 'amigo', 'conocido']:
                relacion = False
            if relacion != 'familiar':
                parentesco = False
            known_lines.append((0, 0, {
                'posee_familiares': 'si' if posee == 't' else 'no',
                'nombre_completo': nombre,
                'relacion': relacion,
                'parentesco': parentesco,
            }))

        medical_values = {
            'enfermedad_persistente': kwargs.get('enfermedad_persistente') or 'no',
            'detalle_enfermedad_persistente': kwargs.get('detalle_enfermedad_persistente') or '',
            'medicacion_continua': kwargs.get('medicacion_continua') or 'no',
            'detalle_medicacion_continua': kwargs.get('detalle_medicacion_continua') or '',
            'enfermedad_laboral': kwargs.get('enfermedad_laboral') or 'no',
            'detalle_enfermedad_laboral': kwargs.get('detalle_enfermedad_laboral') or '',
            'medicacion_continua': kwargs.get('medicacion_continua') or 'no',
            'detalle_medicacion_continua': kwargs.get('detalle_medicacion_continua') or '',
            'cirugia_realizada': kwargs.get('cirugia_realizada') or 'no',
            'detalle_cirugia_realizada': kwargs.get('detalle_cirugia_realizada') or '',
            'discapacidad': kwargs.get('discapacidad') or 'no',
            'tipo_discapacidad': kwargs.get('tipo_discapacidad') or '',
            'porcentaje_discapacidad': kwargs.get('porcentaje_discapacidad') or '',
            'tipo_sangre': kwargs.get('tipo_sangre') or '',
        }

        return {
            'family': family_lines,
            'education': education_lines,
            'experience': experience_lines,
            'references': reference_lines,
            'known': known_lines,
            'medical': medical_values,
        }

    @http.route('/my/application/<int:applicant_id>/update', type='http', auth='user', website=True, methods=['POST'], csrf=True)
    def update_application(self, applicant_id, **kwargs):
        applicant = self._get_owned_applicant(applicant_id)
        if not applicant.portal_update_allowed:
            raise Forbidden(_('Esta postulación ya no está habilitada para actualización.'))

        try:
            applicant_values = self._parse_applicant_values(kwargs, applicant=applicant)
            applicant_values['portal_user_id'] = request.env.user.id

            candidate = applicant.candidate_id.sudo()
            if candidate:
                candidate.write({
                    'firstname': kwargs.get('firstname'),
                    'lastname_paterno': kwargs.get('lastname_paterno'),
                    'lastname_materno': kwargs.get('lastname_materno'),
                })

            child_values = self._build_child_commands(kwargs)

            applicant.write(applicant_values)

            # Reemplazamos los datos repetibles por lo que viene del formulario actualizado.
            applicant.family_ids.unlink()
            applicant.education_ids.unlink()
            applicant.experience_job_ids.unlink()
            applicant.reference_ids.unlink()
            applicant.known_ids.unlink()
            applicant.medical_ids.unlink()

            if child_values['family']:
                applicant.family_ids = child_values['family']
            if child_values['education']:
                applicant.education_ids = child_values['education']
            if child_values['experience']:
                applicant.experience_job_ids = child_values['experience']
            if child_values['references']:
                applicant.reference_ids = child_values['references']
            if child_values['known']:
                applicant.known_ids = child_values['known']
            applicant.medical_ids = [(0, 0, child_values['medical'])]

            # Los nuevos documentos curriculares se agregan sin borrar los existentes.
            new_documents = []
            for file in request.httprequest.files.getlist('curriculumVitae'):
                content, filename = _b64_file(file)
                if content:
                    new_documents.append((0, 0, {'file': content, 'filename': filename}))
            if new_documents:
                for command in new_documents:
                    applicant.env['applicant.document'].sudo().create({
                        'applicant_id': applicant.id,
                        **command[2],
                    })

            applicant.write({'portal_update_allowed': False})
        except (ValidationError, ValueError) as exc:
            _logger.exception('Error actualizando la postulación %s', applicant_id)
            return request.render(
                'custom_web_hr_historial_postulaciones.portal_error',
                {'error_message': str(exc)},
                status=400,
            )
        except Exception:
            _logger.exception('ERROR ACTUALIZANDO POSTULACIÓN')
            return request.render(
                'custom_web_hr_historial_postulaciones.portal_error',
                {'error_message': _('No se pudo actualizar la información. Revise los campos e inténtelo nuevamente.')},
                status=500,
            )

        return request.redirect('/my/application-history')

    def _check_document_extension(self, filename, allowed):
        lower = (filename or '').lower()
        return any(lower.endswith('.' + extension) for extension in allowed)

    @http.route('/my/application/<int:applicant_id>/documentation', type='http', auth='user', website=True, methods=['GET', 'POST'], csrf=True)
    def application_documentation(self, applicant_id, **kwargs):
        applicant = self._get_owned_applicant(applicant_id)
        if not self._documentation_enabled(applicant):
            raise Forbidden(_('El ingreso de documentación aún no está habilitado para esta postulación.'))

        Documentation = request.env['applicant.documentation'].sudo()
        documentation = Documentation.search([('applicant_id', '=', applicant.id)], limit=1)

        if request.httprequest.method == 'POST':
            values = {}
            missing = []
            invalid_files = []

            for field, label, allowed_extensions in DOCUMENT_FIELDS:
                file = request.httprequest.files.get(field)
                if file and file.filename:
                    if not self._check_document_extension(file.filename, allowed_extensions):
                        invalid_files.append(label)
                        continue
                    content = file.read()
                    if content:
                        values[field] = base64.b64encode(content).decode('ascii')
                        values[f'{field}_filename'] = secure_filename(file.filename)
                    elif not documentation or not documentation[field]:
                        missing.append(label)
                elif not documentation or not documentation[field]:
                    missing.append(label)

            if invalid_files:
                return request.render(
                    'custom_web_hr_historial_postulaciones.portal_documentation_form',
                    {
                        'applicant': applicant,
                        'documentation': documentation,
                        'document_fields': DOCUMENT_FIELDS,
                        'errors': [_('Formato no permitido: %s') % label for label in invalid_files],
                        'missing': missing,
                    },
                )

            if missing:
                return request.render(
                    'custom_web_hr_historial_postulaciones.portal_documentation_form',
                    {
                        'applicant': applicant,
                        'documentation': documentation,
                        'document_fields': DOCUMENT_FIELDS,
                        'errors': [_('Falta información: %s') % label for label in missing],
                        'missing': missing,
                    },
                )

            values['applicant_id'] = applicant.id
            try:
                if documentation:
                    documentation.write(values)
                else:
                    documentation = Documentation.create(values)
            except (ValidationError, ValueError) as exc:
                return request.render(
                    'custom_web_hr_historial_postulaciones.portal_documentation_form',
                    {
                        'applicant': applicant,
                        'documentation': documentation,
                        'document_fields': DOCUMENT_FIELDS,
                        'errors': [str(exc)],
                        'missing': [],
                    },
                    status=400,
                )

            return request.redirect('/my/application-documentation')

        return request.render(
            'custom_web_hr_historial_postulaciones.portal_documentation_form',
            {
                'applicant': applicant,
                'documentation': documentation,
                'document_fields': DOCUMENT_FIELDS,
                'errors': [],
                'missing': [],
            },
        )
