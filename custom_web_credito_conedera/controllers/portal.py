import base64
import hmac
import logging
import math
import re
import secrets
import time
from urllib.parse import quote

from markupsafe import escape

from odoo import http, fields, _
from odoo.addons.web.controllers.home import Home
from odoo.exceptions import ValidationError
from odoo.http import request
from werkzeug.exceptions import Forbidden, NotFound
from werkzeug.utils import secure_filename

_logger = logging.getLogger(__name__)
OTP_TTL_SECONDS = 3 * 60
OTP_MAX_ATTEMPTS = 5
MAX_FILE_SIZE = 12 * 1024 * 1024

APPLICATION_FIELDS = [
    'person_type', 'identification', 'application_date', 'applicant_name', 'applicant_email',
    'phone_fixed', 'mobile', 'profession', 'marital_status', 'foreign_residence_time',
    'foreign_work_visa', 'spouse_name', 'spouse_identification', 'spouse_profession',
    'dependents_count', 'home_address', 'housing_type', 'vehicle1_brand', 'vehicle1_model',
    'vehicle1_year', 'vehicle1_value', 'vehicle2_brand', 'vehicle2_model', 'vehicle2_year',
    'vehicle2_value', 'business_name', 'legal_representative', 'business_ruc', 'province',
    'canton', 'city', 'business_address', 'business_phone', 'representative_email',
    'activity_start_date', 'business_local_type', 'monthly_sales', 'social_capital', 'invoice_email',
    'assets_amount', 'monthly_income', 'liabilities_amount', 'monthly_expenses',
    'authorized_buyer_name', 'authorized_buyer_identification', 'authorized_buyer_email',
    'authorized_pickup_name', 'authorized_pickup_identification', 'maps_url', 'employment_company',
    'employment_activity', 'employment_address', 'employment_phone', 'employment_start_date',
    'employment_position', 'employment_salary',
]
DATE_FIELDS = {'application_date', 'activity_start_date', 'employment_start_date'}
INTEGER_FIELDS = {'dependents_count'}
FLOAT_FIELDS = {
    'vehicle1_value', 'vehicle2_value', 'monthly_sales', 'social_capital', 'assets_amount',
    'monthly_income', 'liabilities_amount', 'monthly_expenses', 'employment_salary',
}
DOCUMENT_LABELS = {
    'application_signed': 'Solicitud de crédito preparada y firmada',
    'ruc_updated': 'Copia del RUC actualizado',
    'id_client': 'Cédula a color del cliente',
    'id_spouse': 'Cédula a color del cónyuge',
    'voting_certificate': 'Certificado de votación vigente del cliente',
    'id_legal_representative': 'Cédula a color del representante legal',
    'voting_legal_representative': 'Certificado de votación vigente del representante legal',
    'legal_appointment': 'Nombramiento del representante legal',
    'utility_business': 'Planilla de servicio básico del local',
    'utility_residence': 'Planilla de servicio básico del lugar de residencia',
    'local_photo_inside': 'Fotografía de la parte interna del local',
    'local_photo_outside': 'Fotografía de la parte externa del local',
    'applicant_signing_photo': 'Fotografía del solicitante firmando con el rostro claro',
    'vat_declarations': 'Últimas 6 declaraciones del IVA (archivo consolidado)',
    'income_tax_return': 'Declaración del Impuesto a la Renta del año anterior',
    'bank_certificate': 'Certificado bancario correspondiente a los últimos 6 meses',
}
PHOTO_FIELDS = {'local_photo_inside', 'local_photo_outside', 'applicant_signing_photo'}
DOCUMENT_FIELDS = [
    ('application_signed', 'Solicitud de crédito preparada y firmada'),
    ('ruc_updated', 'Copia del RUC actualizado'),
    ('id_client', 'Cédula a color del cliente'),
    ('id_spouse', 'Cédula a color del cónyuge (si corresponde)'),
    ('voting_certificate', 'Certificado de votación vigente del cliente'),
    ('id_legal_representative', 'Cédula a color del representante legal'),
    ('voting_legal_representative', 'Certificado de votación vigente del representante legal'),
    ('legal_appointment', 'Nombramiento del representante legal'),
    ('utility_business', 'Planilla de servicio básico del local'),
    ('utility_residence', 'Planilla de servicio básico del lugar de residencia'),
    ('local_photo_inside', 'Fotografía de la parte interna del local'),
    ('local_photo_outside', 'Fotografía de la parte externa del local'),
    ('applicant_signing_photo', 'Fotografía del solicitante firmando, con el rostro claramente visible'),
    ('vat_declarations', 'Últimas 6 declaraciones del IVA (archivo consolidado en PDF)'),
    ('income_tax_return', 'Declaración del Impuesto a la Renta del año anterior'),
    ('bank_certificate', 'Certificado bancario correspondiente a los últimos 6 meses'),
]


def _clean(value):
    return str(value or '').strip()


def _parse_date(value):
    value = _clean(value)
    return value or False


def _parse_number(value, label, errors, integer=False):
    value = _clean(value)
    if not value:
        return 0 if integer else 0.0
    try:
        number = int(value) if integer else float(value.replace(',', '.'))
        if not integer and not math.isfinite(number):
            raise ValueError('non-finite number')
        return number
    except (TypeError, ValueError):
        errors.append(_('El campo "%s" debe contener un número válido.') % label)
        return 0 if integer else 0.0


class CreditPortalLogin(Home):
    @http.route()
    def web_login(self, redirect=None, **kw):
        # Solo redirigir por defecto a clientes del portal; los usuarios internos
        # deben conservar el flujo de acceso normal al backend de Odoo.
        explicit_redirect = redirect or request.params.get('redirect')
        response = super().web_login(redirect=explicit_redirect, **kw)
        if not explicit_redirect and request.httprequest.method == 'POST' and request.session.uid:
            user = request.env['res.users'].sudo().browse(request.session.uid).exists()
            if user and user.has_group('base.group_portal') and not user.has_group('base.group_user'):
                return request.redirect('/my/credito/nueva')
        return response


class ConederaCreditPortal(http.Controller):

    def _render_signup(self, values=None):
        context = {'errors': [], 'name': '', 'email': ''}
        context.update(values or {})
        return request.render('custom_web_credito_conedera.portal_credit_signup', context)

    def _render_verify(self, error=None, remaining_seconds=None):
        signup = request.session.get('conedera_credit_signup') or {}
        if remaining_seconds is None:
            remaining_seconds = max(0, int(math.ceil(signup.get('expires', 0) - time.time()))) if signup else 0
        return request.render('custom_web_credito_conedera.portal_credit_verify', {
            'error': error,
            'remaining_seconds': remaining_seconds,
            'signup_email': signup.get('email', ''),
        })

    def _send_otp(self, email, code):
        params = request.env['ir.config_parameter'].sudo()
        email_from = request.env.company.email or params.get_param('mail.default.from')
        if not email_from:
            raise RuntimeError(_('Configure un correo remitente en la compañía o en mail.default.from antes de activar el registro por código.'))
        values = {
            'subject': _('Código de verificación para el portal de crédito CONEDERA'),
            'body_html': (
                '<div style="font-family:Arial,sans-serif;max-width:560px;margin:auto">'
                '<h2 style="color:#8f2f2f">Verificación de correo CONEDERA</h2>'
                '<p>Use el siguiente código para verificar su correo y activar su cuenta:</p>'
                '<p style="font-size:30px;font-weight:bold;letter-spacing:6px">%s</p>'
                '<p>El código vence en 3 minutos. Si no lo ingresa a tiempo, podrá solicitar uno nuevo desde el portal. Si usted no inició este registro, puede ignorar el mensaje.</p>'
                '</div>' % code
            ),
            'email_to': email,
        }
        if email_from:
            values['email_from'] = email_from
        mail = request.env['mail.mail'].sudo().create(values)
        mail.send()
        mail.invalidate_recordset(['state'])
        if mail.state == 'exception':
            raise RuntimeError(_('No se pudo enviar el correo de verificación. Revise el servidor saliente de correo de Odoo.'))

    @http.route('/credito/registro', type='http', auth='public', website=True, methods=['GET', 'POST'], sitemap=False)
    def credit_signup(self, **post):
        if request.httprequest.method == 'GET':
            return self._render_signup()

        name = _clean(post.get('name'))
        email = _clean(post.get('email')).lower()
        password = post.get('password') or ''
        confirm_password = post.get('confirm_password') or ''
        errors = []
        if not name:
            errors.append(_('Ingrese sus nombres y apellidos.'))
        if not email or not re.match(r'^[^\s@]+@[^\s@]+\.[^\s@]+$', email):
            errors.append(_('Ingrese un correo electrónico válido.'))
        if len(password) < 8:
            errors.append(_('La contraseña debe tener al menos 8 caracteres.'))
        if password != confirm_password:
            errors.append(_('Las contraseñas no coinciden.'))
        if post.get('accept_terms') not in ('on', '1', 'true', 'yes'):
            errors.append(_('Debe aceptar el uso de sus datos para gestionar la solicitud de crédito.'))
        existing = request.env['res.users'].sudo().search([
            '|', ('login', '=ilike', email), ('email', '=ilike', email),
        ], limit=1) if email else request.env['res.users']
        if existing:
            errors.append(_('Ya existe una cuenta asociada a ese correo. Ingrese al portal o use recuperación de contraseña.'))
        if errors:
            return self._render_signup({'errors': errors, 'name': name, 'email': email})

        previous_signup = request.session.get('conedera_credit_signup') or {}
        if (previous_signup.get('email') == email and time.time() <= previous_signup.get('expires', 0)):
            return request.redirect('/credito/registro/verificar')

        code = str(secrets.randbelow(900000) + 100000)
        request.session['conedera_credit_signup'] = {
            'name': name,
            'email': email,
            'password': password,
            'code': code,
            'expires': time.time() + OTP_TTL_SECONDS,
            'attempts': 0,
        }
        try:
            self._send_otp(email, code)
        except Exception as exc:
            _logger.exception('No se pudo enviar el código OTP de registro CONEDERA')
            request.session.pop('conedera_credit_signup', None)
            return self._render_signup({
                'errors': [_('No se pudo enviar el código al correo indicado. Verifique la configuración SMTP de Odoo e inténtelo de nuevo.')],
                'name': name,
                'email': email,
            })
        return request.redirect('/credito/registro/verificar')

    @http.route('/credito/registro/verificar', type='http', auth='public', website=True, methods=['GET', 'POST'], sitemap=False)
    def credit_signup_verify(self, **post):
        signup = request.session.get('conedera_credit_signup')
        if not signup:
            return request.redirect('/credito/registro')

        now = time.time()
        expires_at = signup.get('expires', 0)

        # El botón de reenvío solo es aceptado por el servidor una vez vencidos los 3 minutos.
        if request.httprequest.method == 'POST' and post.get('action') == 'resend':
            remaining = max(0, int(math.ceil(expires_at - now)))
            if remaining > 0:
                return self._render_verify(
                    _('Podrá solicitar un código nuevo cuando termine el contador.'),
                    remaining_seconds=remaining,
                )

            code = str(secrets.randbelow(900000) + 100000)
            signup.update({
                'code': code,
                'expires': now + OTP_TTL_SECONDS,
                'attempts': 0,
            })
            request.session['conedera_credit_signup'] = signup
            try:
                self._send_otp(signup['email'], code)
            except Exception:
                _logger.exception('No se pudo reenviar el código OTP de registro CONEDERA')
                # Mantener el registro en sesión y dejar disponible el reenvío si el SMTP falla.
                signup['expires'] = time.time()
                request.session['conedera_credit_signup'] = signup
                return self._render_verify(
                    _('No se pudo enviar el código. Revise la configuración de correo e inténtelo nuevamente.'),
                    remaining_seconds=0,
                )
            return request.redirect('/credito/registro/verificar')

        if request.httprequest.method == 'POST':
            if time.time() > signup.get('expires', 0):
                return self._render_verify(
                    _('El código venció. Solicite uno nuevo con el botón «Enviar código».'),
                    remaining_seconds=0,
                )
            if signup.get('attempts', 0) >= OTP_MAX_ATTEMPTS:
                return self._render_verify(
                    _('Se alcanzó el máximo de intentos para este código. Espere a que termine el contador y solicite un código nuevo.'),
                    remaining_seconds=max(0, int(math.ceil(signup.get('expires', 0) - time.time()))),
                )

            user_code = _clean(post.get('code'))
            signup['attempts'] = signup.get('attempts', 0) + 1
            request.session['conedera_credit_signup'] = signup
            if not hmac.compare_digest(user_code, signup.get('code', '')):
                error = _('El código ingresado no es correcto.')
                return self._render_verify(error)

            existing = request.env['res.users'].sudo().search([
                '|', ('login', '=ilike', signup['email']), ('email', '=ilike', signup['email']),
            ], limit=1)
            if existing:
                request.session.pop('conedera_credit_signup', None)
                return request.redirect('/web/login?account_exists=1')
            try:
                portal_group = request.env.ref('base.group_portal')
                user = request.env['res.users'].sudo().with_context(no_reset_password=True, mail_create_nosubscribe=True).create({
                    'name': signup['name'],
                    'login': signup['email'],
                    'email': signup['email'],
                    'password': signup['password'],
                    'groups_id': [(6, 0, [portal_group.id])],
                })
                user.partner_id.sudo().write({'email': signup['email'], 'name': signup['name']})
                request.session.pop('conedera_credit_signup', None)
                return request.redirect('/web/login?account_created=1&redirect=%s' % quote('/my/credito/nueva', safe=''))
            except Exception:
                _logger.exception('No se pudo crear la cuenta portal de crédito CONEDERA')
                return self._render_verify(_('No se pudo crear la cuenta. Revise la configuración de usuarios y vuelva a intentarlo.'))

        return self._render_verify()

    def _get_owned_application(self, application_id):
        application = request.env['conedera.credit.application'].sudo().browse(application_id).exists()
        if not application or application.portal_user_id.id != request.env.user.id:
            raise NotFound()
        return application

    def _portal_applications(self, domain=None):
        domain = list(domain or [])
        domain.append(('portal_user_id', '=', request.env.user.id))
        return request.env['conedera.credit.application'].sudo().search(domain, order='create_date desc, id desc')

    def _render_application_form(self, form_values=None, errors=None):
        defaults = {'application_date': fields.Date.context_today(request.env.user).strftime('%Y-%m-%d'),
                    'applicant_name': request.env.user.name,
                    'applicant_email': request.env.user.email or request.env.user.login}
        defaults.update(form_values or {})
        return request.render('custom_web_credito_conedera.portal_credit_application_form', {
            'form_values': defaults,
            'errors': errors or [],
            'marital_statuses': [
                ('single', 'Soltero/a'), ('married', 'Casado/a'), ('divorced', 'Divorciado/a'),
                ('widowed', 'Viudo/a'), ('free_union', 'Unión de hecho'), ('other', 'Otro'),
            ],
            'housing_types': [('own', 'Propia'), ('rented', 'Alquilada'), ('family', 'Familiares'), ('mortgaged', 'Hipotecada')],
            'local_types': [('own', 'Propio'), ('rented', 'Alquilado'), ('family', 'Familiar'), ('mortgaged', 'Hipotecado')],
        })

    @http.route('/my/credito/nueva', type='http', auth='user', website=True, methods=['GET'], sitemap=False)
    def new_credit_application(self, **kwargs):
        return self._render_application_form({'applicant_name': request.env.user.name, 'applicant_email': request.env.user.email or request.env.user.login})

    def _reference_commands(self, post, errors):
        commands = []
        for number in range(1, 4):
            commercial = {
                'reference_type': 'commercial', 'sequence': number * 10,
                'provider': _clean(post.get('commercial_provider_%s' % number)),
                'customer_since': _clean(post.get('commercial_since_%s' % number)),
                'credit_limit': _parse_number(post.get('commercial_limit_%s' % number), _('Cupo de referencia comercial %s') % number, errors),
                'term': _clean(post.get('commercial_term_%s' % number)),
                'phone': _clean(post.get('commercial_phone_%s' % number)),
                'contact': _clean(post.get('commercial_contact_%s' % number)),
            }
            if any(commercial[key] not in ('', 0, 0.0, False) for key in ('provider', 'customer_since', 'credit_limit', 'term', 'phone', 'contact')):
                commands.append((0, 0, commercial))
            personal = {
                'reference_type': 'personal', 'sequence': number * 10,
                'person_name': _clean(post.get('personal_name_%s' % number)),
                'address': _clean(post.get('personal_address_%s' % number)),
                'home_phone': _clean(post.get('personal_phone_%s' % number)),
                'relationship': _clean(post.get('personal_relationship_%s' % number)),
            }
            if any(personal[key] for key in ('person_name', 'address', 'home_phone', 'relationship')):
                commands.append((0, 0, personal))
            bank = {
                'reference_type': 'bank', 'sequence': number * 10,
                'bank_name': _clean(post.get('bank_name_%s' % number)),
                'account_number': _clean(post.get('bank_account_%s' % number)),
                'opening_date': _parse_date(post.get('bank_opening_%s' % number)),
                'account_type': _clean(post.get('bank_type_%s' % number)) or False,
            }
            if any(bank[key] for key in ('bank_name', 'account_number', 'opening_date', 'account_type')):
                commands.append((0, 0, bank))
        return commands

    @http.route('/my/credito/solicitud/enviar', type='http', auth='user', website=True, methods=['POST'], sitemap=False)
    def submit_credit_application(self, **post):
        errors = []
        values = {}
        for field_name in APPLICATION_FIELDS:
            value = post.get(field_name)
            if field_name in DATE_FIELDS:
                values[field_name] = _parse_date(value)
            elif field_name in INTEGER_FIELDS:
                values[field_name] = _parse_number(value, field_name, errors, integer=True)
            elif field_name in FLOAT_FIELDS:
                values[field_name] = _parse_number(value, field_name, errors)
            else:
                values[field_name] = _clean(value) or False
        values['application_date'] = values.get('application_date') or fields.Date.context_today(request.env.user).strftime('%Y-%m-%d')
        values['portal_user_id'] = request.env.user.id
        values['declaration_accepted'] = post.get('declaration_accepted') in ('on', '1', 'true', 'yes')
        consent_fields = [
            ('prior_commercial_relationship_accepted', _('Debe aceptar la cláusula sobre la relación comercial previa y su valor probatorio.')),
            ('electronic_service_accepted', _('Debe aceptar la cláusula de citación telemática propuesta conforme al Art. 55.1 del COGEP.')),
            ('credit_bureau_authorized', _('Debe autorizar por separado la consulta de su score e historial crediticio.')),
            ('company_signature_stamp_acknowledged', _('Debe confirmar que conoce el requisito de firma y sello del representante legal de CONEDERA S.A.')),
            ('additional_financial_documents_accepted', _('Debe aceptar la entrega de los documentos financieros adicionales solicitados.')),
        ]
        for field_name, _message in consent_fields:
            values[field_name] = post.get(field_name) in ('on', '1', 'true', 'yes')
        values['reference_ids'] = self._reference_commands(post, errors)

        for field_name, label in [
            ('person_type', _('tipo de solicitante')),
            ('identification', _('cédula o RUC del solicitante')),
            ('applicant_name', _('nombres y apellidos')),
            ('applicant_email', _('correo electrónico')),
            ('mobile', _('celular')),
            ('business_name', _('nombre o razón social')),
            ('business_ruc', _('RUC del negocio')),
            ('business_address', _('dirección de la empresa')),
        ]:
            if not values.get(field_name):
                errors.append(_('El campo %(field)s es obligatorio.') % {'field': label})
        if values.get('person_type') not in ('natural', 'juridical'):
            errors.append(_('Seleccione persona natural o persona jurídica.'))
        if values.get('applicant_email') and not re.match(r'^[^\s@]+@[^\s@]+\.[^\s@]+$', values['applicant_email']):
            errors.append(_('Ingrese un correo válido para el propietario o representante.'))
        if values.get('maps_url') and not values['maps_url'].lower().startswith(('https://', 'http://')):
            errors.append(_('El enlace de Google Maps debe comenzar con http:// o https://.'))
        if not values['declaration_accepted']:
            errors.append(_('Debe aceptar la declaración y autorización general para enviar la solicitud.'))
        for field_name, message in consent_fields:
            if not values[field_name]:
                errors.append(message)
        if errors:
            return self._render_application_form(post, errors)

        try:
            application = request.env['conedera.credit.application'].sudo().create(values)
        except (ValidationError, ValueError) as exc:
            return self._render_application_form(post, [str(exc)])
        except Exception:
            _logger.exception('Error registrando la solicitud de crédito desde el portal')
            return self._render_application_form(post, [_('No se pudo registrar la solicitud. Revise los datos e inténtelo nuevamente.')])

        # El PDF de referencia indica remitir a cobranzas@viteltek.com el enlace de Google Maps del negocio.
        if application.maps_url:
            try:
                email_from = request.env.company.email or request.env['ir.config_parameter'].sudo().get_param('mail.default.from') or False
                mail_vals = {
                    'subject': _('Ubicación de negocio - Solicitud de crédito %s') % application.name,
                    'body_html': (
                        '<p>Se registró una solicitud de crédito CONEDERA.</p>'
                        '<p><b>Solicitud:</b> %s<br/><b>Solicitante:</b> %s<br/>'
                        '<b>Negocio:</b> %s<br/><b>Identificación:</b> %s</p>'
                        '<p><b>Ubicación Google Maps:</b> <a href="%s">%s</a></p>'
                    ) % tuple(escape(value or '') for value in (application.name, application.applicant_name, application.business_name, application.identification, application.maps_url, application.maps_url)),
                    'email_to': 'cobranzas@viteltek.com',
                }
                if email_from:
                    mail_vals['email_from'] = email_from
                request.env['mail.mail'].sudo().create(mail_vals).send()
            except Exception:
                _logger.exception('No se pudo enviar el enlace de Maps al buzón indicado en el formulario CONEDERA')
        return request.redirect('/my/credito/%s?sent=1' % application.id)

    @http.route('/my/credito/historial', type='http', auth='user', website=True, methods=['GET'], sitemap=False)
    def credit_history(self, **kwargs):
        return request.render('custom_web_credito_conedera.portal_credit_history', {
            'applications': self._portal_applications(),
        })

    @http.route('/my/credito/<int:application_id>', type='http', auth='user', website=True, methods=['GET'], sitemap=False)
    def credit_application_detail(self, application_id, **kwargs):
        application = self._get_owned_application(application_id)
        history = application.history_ids.filtered(lambda row: row.visible_to_portal).sorted(key=lambda row: (row.date or fields.Datetime.now(), row.id))
        documents = application.document_ids[:1]
        return request.render('custom_web_credito_conedera.portal_credit_detail', {
            'application': application,
            'history': history,
            'documents': documents,
        })

    @http.route('/my/credito/documentos', type='http', auth='user', website=True, methods=['GET'], sitemap=False)
    def credit_documents_index(self, **kwargs):
        applications = self._portal_applications([('documents_unlocked', '=', True)])
        applications = applications.filtered(lambda app: not app.stage_id.is_rejected)
        return request.render('custom_web_credito_conedera.portal_credit_documents_index', {'applications': applications})

    def _credit_document_errors(self, doc):
        missing = []
        if doc:
            for field_name in doc._required_fields():
                if not doc[field_name]:
                    missing.append(DOCUMENT_LABELS.get(field_name, field_name))
        return missing

    def _render_credit_documents_form(self, application, document=None, errors=None):
        return request.render('custom_web_credito_conedera.portal_credit_documents_form', {
            'application': application,
            'document': document,
            'errors': errors or [],
            'document_fields': DOCUMENT_FIELDS,
            'photo_fields': PHOTO_FIELDS,
        })

    @http.route('/my/credito/<int:application_id>/documentos', type='http', auth='user', website=True, methods=['GET', 'POST'], sitemap=False)
    def credit_documents_form(self, application_id, **post):
        application = self._get_owned_application(application_id)
        if not application.documents_unlocked or application.stage_id.is_rejected:
            raise Forbidden(_('El ingreso de documentos se habilita cuando la solicitud está aprobada.'))
        Documents = request.env['conedera.credit.documents'].sudo()
        document = Documents.search([('application_id', '=', application.id)], limit=1)
        if request.httprequest.method == 'GET':
            return self._render_credit_documents_form(application, document)

        values = {}
        errors = []
        uploaded_any = False
        common_doc_fields = {'application_signed', 'ruc_updated', 'utility_business', 'utility_residence', 'local_photo_inside', 'local_photo_outside', 'applicant_signing_photo', 'vat_declarations', 'income_tax_return', 'bank_certificate'}
        natural_doc_fields = {'id_client', 'id_spouse', 'voting_certificate'}
        juridical_doc_fields = {'id_legal_representative', 'voting_legal_representative', 'legal_appointment'}
        allowed_fields = common_doc_fields | (natural_doc_fields if application.person_type == 'natural' else juridical_doc_fields)
        if application.person_type == 'natural' and not application.spouse_name:
            allowed_fields.discard('id_spouse')
        for field_name, label in DOCUMENT_FIELDS:
            if field_name not in allowed_fields:
                continue
            file_obj = request.httprequest.files.get(field_name)
            if not file_obj or not file_obj.filename:
                continue
            filename = secure_filename(file_obj.filename) or 'documento'
            content = file_obj.read()
            if not content:
                continue
            if len(content) > MAX_FILE_SIZE:
                errors.append(_('El archivo "%s" supera el límite de 12 MB.') % label)
                continue
            lowered = filename.lower()
            allowed = ('.jpg', '.jpeg', '.png') if field_name in PHOTO_FIELDS else ('.pdf', '.jpg', '.jpeg', '.png')
            if not lowered.endswith(allowed):
                errors.append(_('El archivo "%s" debe estar en formato %s.') % (label, 'JPG o PNG' if field_name in PHOTO_FIELDS else 'PDF, JPG o PNG'))
                continue
            values[field_name] = base64.b64encode(content).decode('ascii')
            values['%s_filename' % field_name] = filename
            uploaded_any = True

        if errors:
            return self._render_credit_documents_form(application, document, errors)
        if not document:
            values['application_id'] = application.id
            values['last_portal_upload'] = fields.Datetime.now() if uploaded_any else False
            try:
                document = Documents.create(values)
            except (ValidationError, ValueError) as exc:
                return self._render_credit_documents_form(application, document, [str(exc)])
        else:
            if uploaded_any:
                values['last_portal_upload'] = fields.Datetime.now()
                values['state'] = 'pending'
            try:
                document.write(values)
            except (ValidationError, ValueError) as exc:
                return self._render_credit_documents_form(application, document, [str(exc)])

        missing = self._credit_document_errors(document)
        if not missing:
            document.action_mark_submitted()
            return request.redirect('/my/credito/documentos?uploaded=1')
        return self._render_credit_documents_form(
            application, document,
            [_('Documentación guardada, pero aún faltan: %s.') % ', '.join(missing)],
        )
