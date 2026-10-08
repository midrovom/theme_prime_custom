import base64
import json
import logging
import re

from werkzeug.exceptions import Forbidden, NotFound
from werkzeug.utils import secure_filename

from odoo import fields, http, _
from odoo.http import request
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

    @http.route('/my/application/form-catalogs', type='http', auth='user', website=True, methods=['GET'], csrf=False)
    def application_form_catalogs(self, **kwargs):
        """Return all static catalogs needed by the native recruitment form in one request."""
        countries = request.env['res.country'].sudo().search_read([], ['id', 'name'], order='name ASC')
        states = request.env['res.country.state'].sudo().search_read([], ['id', 'name', 'country_id'], order='name ASC')
        study_levels = request.env['hr.recruitment.degree'].sudo().search_read([], ['id', 'name'], order='id ASC')

        states_by_country = {}
        for state in states:
            country = state.get('country_id')
            country_id = country[0] if isinstance(country, (list, tuple)) else country
            if country_id:
                states_by_country.setdefault(str(country_id), []).append({
                    'id': state['id'],
                    'name': state['name'],
                })

        payload = {
            'ok': True,
            'countries': countries,
            'states_by_country': states_by_country,
            'study_levels': study_levels,
        }
        return request.make_response(
            json.dumps(payload, ensure_ascii=False),
            headers=[('Content-Type', 'application/json; charset=utf-8'), ('Cache-Control', 'public, max-age=1800')],
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
            '/jobs/recruitment/%s?edit_applicant=%s' % (applicant.job_id.id, applicant.id)
        )

    def _field_value(self, record, field_name, default=False):
        """Return a field value without crashing if a custom installation lacks it."""
        if not record or field_name not in record._fields:
            return default
        try:
            return record[field_name]
        except Exception:
            _logger.exception("No se pudo leer %s.%s", record._name, field_name)
            return default

    @http.route('/my/application/<int:applicant_id>/image', type='http', auth='user', website=True, methods=['GET'], csrf=False)
    def application_image(self, applicant_id, **kwargs):
        applicant = self._get_owned_applicant(applicant_id)
        image = self._field_value(applicant, 'image_1920', False)
        if not image:
            raise NotFound()
        try:
            content = base64.b64decode(image)
        except Exception:
            raise NotFound()
        if content.startswith(b'\x89PNG\r\n\x1a\n'):
            content_type = 'image/png'
            extension = 'png'
        elif content.startswith(b'\xff\xd8\xff'):
            content_type = 'image/jpeg'
            extension = 'jpg'
        else:
            content_type = 'image/jpeg'
            extension = 'jpg'
        return request.make_response(
            content,
            headers=[
                ('Content-Type', content_type),
                ('Content-Disposition', 'inline; filename="foto_%s.%s"' % (applicant.id, extension)),
                ('Cache-Control', 'private, max-age=60'),
            ],
        )

    @http.route('/my/application/<int:applicant_id>/document/<int:document_id>', type='http', auth='user', website=True, methods=['GET'], csrf=False)
    def application_document_file(self, applicant_id, document_id, **kwargs):
        applicant = self._get_owned_applicant(applicant_id)
        document = request.env['applicant.document'].sudo().browse(document_id).exists()
        if not document or document.applicant_id.id != applicant.id or not document.file:
            raise NotFound()
        try:
            content = base64.b64decode(document.file)
        except Exception:
            raise NotFound()
        filename = secure_filename(document.filename or ('documento_%s.pdf' % document.id)) or ('documento_%s.pdf' % document.id)
        return request.make_response(
            content,
            headers=[
                ('Content-Type', 'application/pdf'),
                ('Content-Disposition', 'inline; filename="%s"' % filename),
                ('Cache-Control', 'private, max-age=60'),
            ],
        )

    @http.route('/my/application/<int:applicant_id>/data', type='http', auth='user', website=True, methods=['GET'], csrf=False)
    def application_data(self, applicant_id, **kwargs):
        try:
            applicant = self._get_owned_applicant(applicant_id)
            candidate = self._field_value(applicant, 'candidate_id')
            birthdate = self._field_value(applicant, 'birthdate')
            code_cell, cellphone = _split_phone(self._field_value(applicant, 'partner_mobile', ''))
            code_phone, phone = _split_phone(self._field_value(applicant, 'partner_phone', ''))

            medical_ids = self._field_value(applicant, 'medical_ids', request.env['applicant.medical'])
            medical = medical_ids[:1] if medical_ids else False
            medical_fields = [
                'enfermedad_persistente', 'detalle_enfermedad_persistente',
                'medicacion_continua', 'detalle_medicacion_continua',
                'enfermedad_laboral', 'detalle_enfermedad_laboral',
                'cirugia_realizada', 'detalle_cirugia_realizada',
                'discapacidad', 'tipo_discapacidad', 'porcentaje_discapacidad',
                'tipo_sangre',
            ]
            medical_values = {
                field: self._field_value(medical, field, '')
                for field in medical_fields
            }

            family_ids = self._field_value(applicant, 'family_ids', request.env['applicant.family'])
            education_ids = self._field_value(applicant, 'education_ids', request.env['applicant.education'])
            experience_ids = self._field_value(applicant, 'experience_job_ids', request.env['applicant.experience.job'])
            known_ids = self._field_value(applicant, 'known_ids', request.env['applicant.known'])
            reference_ids = self._field_value(applicant, 'reference_ids', request.env['applicant.reference'])
            document_ids = self._field_value(applicant, 'document_ids', request.env['applicant.document'])

            candidate_id = candidate.id if candidate else False
            applicant_image = self._field_value(applicant, 'image_1920', False)
            portal_user = self._field_value(applicant, 'portal_user_id', False)
            portal_user_id = portal_user.id if portal_user else False

            payload = {
                'ok': True,
                'id': applicant.id,
                'job_id': self._field_value(self._field_value(applicant, 'job_id'), 'id', False),
                'portal_user_id': portal_user_id,
                'has_image': bool(applicant_image),
                'image_url': f'/my/application/{applicant.id}/image' if applicant_image else False,
                'has_curriculum': bool(document_ids),
                'documents': [],
                'firstname': self._field_value(candidate, 'firstname', ''),
                'lastname_paterno': self._field_value(candidate, 'lastname_paterno', ''),
                'lastname_materno': self._field_value(candidate, 'lastname_materno', ''),
                'age': self._field_value(applicant, 'age', ''),
                'address': self._field_value(applicant, 'address', ''),
                'parish': self._field_value(applicant, 'parish', ''),
                'birth_country_id': self._field_value(self._field_value(applicant, 'birth_country_id'), 'id', False),
                'provincia_id': self._field_value(self._field_value(applicant, 'provincia_id'), 'id', False),
                'birthdate': {
                    'day': birthdate.day if birthdate else '',
                    'month': birthdate.month if birthdate else '',
                    'year': birthdate.year if birthdate else '',
                },
                'phone_code': code_phone,
                'phone': phone,
                'cellphone_code': code_cell,
                'cellphone': cellphone,
                'vive_con': self._field_value(applicant, 'vive_con', ''),
                'tipo_vivienda': self._field_value(applicant, 'tipo_vivienda', ''),
                'num_hijos': self._field_value(applicant, 'num_hijos', 0),
                'dependientes': [x.strip() for x in _clean(self._field_value(applicant, 'dependientes', '')).split(',') if x.strip()],
                'email': self._field_value(applicant, 'email_from', '') or _clean(request.env.user.email),
                'document_type': self._field_value(applicant, 'document_type', ''),
                'document_number': self._field_value(applicant, 'cedula', ''),
                'nationality': self._field_value(applicant, 'nacionality', ''),
                'estado_civil': self._field_value(applicant, 'estado_civil', ''),
                'secondary_studies': bool(self._field_value(applicant, 'secondary_studies', False)),
                'disability': bool(self._field_value(applicant, 'disability', False)),
                'family_disability': bool(self._field_value(applicant, 'family_disability', False)),
                'medical': medical_values,
                'family': [],
                'education': [],
                'experience': [],
                'known': {
                    'posee': False,
                    'nombre': '',
                    'relacion': '',
                    'parentesco': '',
                },
                'references': [],
            }

            for document in document_ids.sorted('id'):
                payload['documents'].append({
                    'id': document.id,
                    'filename': self._field_value(document, 'filename', '') or f'documento_{document.id}.pdf',
                    'url': f'/my/application/{applicant.id}/document/{document.id}',
                })

            for family in family_ids.sorted('id'):
                payload['family'].append({
                    'id': family.id,
                    'familiar_type': self._field_value(family, 'familiar_type', ''),
                    'name': self._field_value(family, 'name', ''),
                    'fallecido': bool(self._field_value(family, 'fallecido', False)),
                    'no_tiene': bool(self._field_value(family, 'no_tiene', False)),
                    'document_type': self._field_value(family, 'document_type', ''),
                    'cedula': self._field_value(family, 'cedula', ''),
                    'birthdate': str(self._field_value(family, 'birthdate', '')) if self._field_value(family, 'birthdate', False) else '',
                    'phone': self._field_value(family, 'phone', ''),
                    'occupation': self._field_value(family, 'occupation', ''),
                    'economically_dependent': self._field_value(family, 'economically_dependent', ''),
                    'disability': self._field_value(family, 'disability', ''),
                    'disability_type': self._field_value(family, 'disability_type', ''),
                    'disability_percentage': self._field_value(family, 'disability_percentage', ''),
                    'has_document': bool(self._field_value(family, 'document_file', False)),
                    'filename': self._field_value(family, 'filename', ''),
                })

            for education in education_ids.sorted('id'):
                level = self._field_value(education, 'level_id')
                country = self._field_value(education, 'country_id')
                state = self._field_value(education, 'state_id')
                start_date = self._field_value(education, 'fecha_inicio', False)
                payload['education'].append({
                    'level_id': level.id if level else False,
                    'institucion': self._field_value(education, 'institucion', ''),
                    'fecha_inicio': str(start_date) if start_date else '',
                    'year_fin': self._field_value(education, 'year_fin', ''),
                    'country_id': country.id if country else False,
                    'state_id': state.id if state else False,
                    'titulo': self._field_value(education, 'titulo', ''),
                    'titulo_por_obtener': self._field_value(education, 'titulo_por_obtener', ''),
                    'institucion_2': self._field_value(education, 'institucion_2', ''),
                    'horario': self._field_value(education, 'horario', ''),
                    'carrera': self._field_value(education, 'carrera', ''),
                    'estado': self._field_value(education, 'estado', ''),
                    'study_current': self._field_value(education, 'study_current', ''),
                })

            for exp in experience_ids.sorted('id'):
                country = self._field_value(exp, 'country_id')
                state = self._field_value(exp, 'state_id')
                start_date = self._field_value(exp, 'fecha_inicio', False)
                payload['experience'].append({
                    'name': self._field_value(exp, 'name', ''),
                    'empresa': self._field_value(exp, 'empresa', ''),
                    'country_id': country.id if country else False,
                    'state_id': state.id if state else False,
                    'fecha_inicio': str(start_date) if start_date else '',
                    'year_fin': self._field_value(exp, 'year_fin', ''),
                    'tiempo_servicio': self._field_value(exp, 'tiempo_servicio', ''),
                    'telefonos': self._field_value(exp, 'telefonos', ''),
                    'ingreso_mensual': self._field_value(exp, 'ingreso_mensual', 0),
                    'motivo_separacion': self._field_value(exp, 'motivo_separacion', ''),
                    'jefe_directo': self._field_value(exp, 'jefe_directo', ''),
                    'cargo_jefe_directo': self._field_value(exp, 'cargo_jefe_directo', ''),
                })

            known = known_ids[:1] if known_ids else False
            if known:
                payload['known'] = {
                    'posee': self._field_value(known, 'posee_familiares', '') == 'si',
                    'nombre': self._field_value(known, 'nombre_completo', ''),
                    'relacion': self._field_value(known, 'relacion', ''),
                    'parentesco': self._field_value(known, 'parentesco', ''),
                }

            for ref in reference_ids.sorted('id'):
                payload['references'].append({
                    'nombre': self._field_value(ref, 'nombre', ''),
                    'domicilio': self._field_value(ref, 'domicilio', ''),
                    'telefono': self._field_value(ref, 'telefono', ''),
                    'ocupacion': self._field_value(ref, 'ocupacion', ''),
                    'tiempo_conocerlo': self._field_value(ref, 'tiempo_conocerlo', ''),
                })

            # DEBUG TEMPORAL: registrar exactamente lo que el backend prepara
            # para el formulario de actualización. No se modifica la respuesta ni
            # la lógica de precarga; solo se agrega trazabilidad en el log de Odoo.
            _logger.info(
                'PORTAL_PRELOAD applicant=%s user=%s counts={family:%s, education:%s, experience:%s, references:%s} payload=%s',
                applicant.id,
                request.env.user.id,
                len(payload['family']),
                len(payload['education']),
                len(payload['experience']),
                len(payload['references']),
                json.dumps(payload, default=str, ensure_ascii=False),
            )

            return request.make_response(
                json.dumps(payload, default=str),
                headers=[('Content-Type', 'application/json; charset=utf-8'), ('Cache-Control', 'no-store')],
            )
        except (NotFound, Forbidden):
            raise
        except Exception as exc:
            _logger.exception('ERROR CARGANDO INFORMACIÓN DE LA POSTULACIÓN %s', applicant_id)
            error_payload = {
                'ok': False,
                'error': str(exc),
                'applicant_id': applicant_id,
            }
            return request.make_response(
                json.dumps(error_payload, default=str),
                headers=[('Content-Type', 'application/json; charset=utf-8'), ('Cache-Control', 'no-store'), ('X-Portal-Error', '1')],
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

    def _build_child_commands(self, kwargs, applicant=None):
        family_lines = []
        existing_families = {}
        if applicant:
            existing_families = {str(rec.id): rec for rec in applicant.family_ids}

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

            original = existing_families.get(str(kwargs.get(f'famOriginalId_{k}') or ''))

            document_type = False if fallecido else kwargs.get(f'famTipoDoc_{k}')
            document_file = False
            filename = False

            # Si el usuario no seleccionó un nuevo PDF, conservamos el que ya
            # estaba registrado para ese familiar.
            uploaded = request.httprequest.files.get(f'famArchivo_{k}')
            if uploaded and getattr(uploaded, 'filename', ''):
                content = uploaded.read()
                if content:
                    document_file = base64.b64encode(content)
                    filename = secure_filename(uploaded.filename) or uploaded.filename

            if not document_file and original and original.document_file and not fallecido and not no_tiene:
                document_file = original.document_file
                filename = original.filename

            family_lines.append((0, 0, {
                'name': name,
                'familiar_type': str(tipo) if tipo else False,
                'fallecido': fallecido,
                'no_tiene': no_tiene,
                'document_type': document_type,
                'birthdate': False if fallecido else kwargs.get(f'famFecha_{k}'),
                'phone': False if fallecido else kwargs.get(f'famTelefono_{k}'),
                'occupation': False if fallecido else kwargs.get(f'famOcupacion_{k}'),
                'economically_dependent': False if fallecido else kwargs.get(f'famDepende_{k}'),
                'disability': False if fallecido else kwargs.get(f'famDisc_{k}'),
                'disability_type': False if fallecido else kwargs.get(f'famDiscTipo_{k}'),
                'disability_percentage': False if fallecido else kwargs.get(f'famDiscPorcentaje_{k}'),
                'cedula': False if fallecido else kwargs.get(f'famCedula_{k}'),
                'filename': filename,
                'document_file': document_file,
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

            child_values = self._build_child_commands(kwargs, applicant=applicant)

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
