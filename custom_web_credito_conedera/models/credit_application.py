import logging
from markupsafe import escape

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class ConederaCreditApplication(models.Model):
    _name = 'conedera.credit.application'
    _description = 'Solicitud de crédito CONEDERA S.A.'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc, id desc'

    name = fields.Char(string='Número de solicitud', required=True, copy=False, readonly=True, default='Nuevo', tracking=True, index=True)
    active = fields.Boolean(default=True)
    portal_user_id = fields.Many2one('res.users', string='Usuario del portal', required=True, readonly=True, index=True, ondelete='restrict')
    person_type = fields.Selection([
        ('natural', 'Persona natural'),
        ('juridical', 'Persona jurídica'),
    ], string='Tipo de solicitante', required=True, tracking=True)
    identification = fields.Char(string='Cédula o RUC del solicitante', required=True, tracking=True, index=True)
    application_date = fields.Date(string='Lugar y fecha de solicitud', required=True, default=fields.Date.context_today)
    applicant_name = fields.Char(string='Nombres y apellidos del propietario o representante', required=True, tracking=True)
    applicant_email = fields.Char(string='Correo electrónico del propietario o representante', required=True)
    phone_fixed = fields.Char(string='Teléfono fijo')
    mobile = fields.Char(string='Celular', required=True)
    profession = fields.Char(string='Profesión')
    marital_status = fields.Selection([
        ('single', 'Soltero/a'), ('married', 'Casado/a'), ('divorced', 'Divorciado/a'),
        ('widowed', 'Viudo/a'), ('free_union', 'Unión de hecho'), ('other', 'Otro'),
    ], string='Estado civil')
    foreign_residence_time = fields.Char(string='Tiempo de residencia (extranjero)')
    foreign_work_visa = fields.Selection([('yes', 'Sí'), ('no', 'No')], string='Visa de trabajo (extranjero)')
    spouse_name = fields.Char(string='Nombres y apellidos del cónyuge')
    spouse_identification = fields.Char(string='Cédula del cónyuge')
    spouse_profession = fields.Char(string='Profesión del cónyuge')
    dependents_count = fields.Integer(string='Número de cargas')
    home_address = fields.Char(string='Dirección domiciliaria')
    housing_type = fields.Selection([
        ('own', 'Propia'), ('rented', 'Alquilada'), ('family', 'Familiares'), ('mortgaged', 'Hipotecada'),
    ], string='Vivienda')

    vehicle1_brand = fields.Char(string='Vehículo 1 - marca')
    vehicle1_model = fields.Char(string='Vehículo 1 - modelo')
    vehicle1_year = fields.Char(string='Vehículo 1 - año')
    vehicle1_value = fields.Monetary(string='Vehículo 1 - avalúo comercial', currency_field='currency_id')
    vehicle2_brand = fields.Char(string='Vehículo 2 - marca')
    vehicle2_model = fields.Char(string='Vehículo 2 - modelo')
    vehicle2_year = fields.Char(string='Vehículo 2 - año')
    vehicle2_value = fields.Monetary(string='Vehículo 2 - avalúo comercial', currency_field='currency_id')

    business_name = fields.Char(string='Nombre o razón social', required=True, tracking=True)
    legal_representative = fields.Char(string='Nombre del representante legal')
    business_ruc = fields.Char(string='RUC del negocio', required=True, index=True)
    province = fields.Char(string='Provincia')
    canton = fields.Char(string='Cantón')
    city = fields.Char(string='Ciudad')
    business_address = fields.Char(string='Dirección de la empresa', required=True)
    business_phone = fields.Char(string='Teléfono de la empresa')
    representative_email = fields.Char(string='Correo del representante legal')
    activity_start_date = fields.Date(string='Fecha de inicio de actividades')
    business_local_type = fields.Selection([
        ('own', 'Propio'), ('rented', 'Alquilado'), ('family', 'Familiar'), ('mortgaged', 'Hipotecado'),
    ], string='Local')
    monthly_sales = fields.Monetary(string='Promedio de ventas mensuales', currency_field='currency_id')
    social_capital = fields.Monetary(string='Capital social', currency_field='currency_id')
    invoice_email = fields.Char(string='Correo para facturas')
    assets_amount = fields.Monetary(string='Activos (monto aproximado)', currency_field='currency_id')
    monthly_income = fields.Monetary(string='Ingresos mensuales', currency_field='currency_id')
    liabilities_amount = fields.Monetary(string='Pasivos (monto aproximado)', currency_field='currency_id')
    monthly_expenses = fields.Monetary(string='Gastos mensuales', currency_field='currency_id')
    authorized_buyer_name = fields.Char(string='Persona autorizada a comprar')
    authorized_buyer_identification = fields.Char(string='Cédula de persona autorizada a comprar')
    authorized_buyer_email = fields.Char(string='Correo de persona autorizada a comprar')
    authorized_pickup_name = fields.Char(string='Persona autorizada a retirar mercadería')
    authorized_pickup_identification = fields.Char(string='Cédula de persona autorizada a retirar mercadería')
    maps_url = fields.Char(string='Enlace de ubicación de Google Maps', help='El PDF de CONEDERA indica enviar esta ubicación a cobranzas@viteltek.com.')

    employment_company = fields.Char(string='Empresa donde trabaja (relación de dependencia)')
    employment_activity = fields.Char(string='Actividad de la empresa')
    employment_address = fields.Char(string='Dirección de la empresa donde trabaja')
    employment_phone = fields.Char(string='Teléfono de empresa donde trabaja')
    employment_start_date = fields.Date(string='Fecha de ingreso al empleo')
    employment_position = fields.Char(string='Cargo')
    employment_salary = fields.Monetary(string='Sueldo', currency_field='currency_id')

    reference_ids = fields.One2many('conedera.credit.reference', 'application_id', string='Referencias')
    history_ids = fields.One2many('conedera.credit.stage.history', 'application_id', string='Historial de etapas', readonly=True)
    document_ids = fields.One2many('conedera.credit.documents', 'application_id', string='Documentos solicitados', copy=False)
    document_complete = fields.Boolean(string='Documentación completa', compute='_compute_document_complete')

    stage_id = fields.Many2one(
        'conedera.credit.stage', string='Etapa', tracking=True, index=True,
        group_expand='_read_group_stage_ids', ondelete='restrict',
        default=lambda self: self.env['conedera.credit.stage'].search([('is_initial', '=', True)], order='sequence,id', limit=1),
    )
    documents_unlocked = fields.Boolean(string='Ingreso documental habilitado', default=False, copy=False, readonly=True, tracking=True)
    currency_id = fields.Many2one('res.currency', string='Moneda', default=lambda self: self.env.company.currency_id, required=True)
    declaration_accepted = fields.Boolean(string='Declaración y autorización general aceptada', required=True, default=False, tracking=True)
    prior_commercial_relationship_accepted = fields.Boolean(string='Acepta cláusula de relación comercial previa', default=False, tracking=True)
    electronic_service_accepted = fields.Boolean(string='Acepta citación telemática (Art. 55.1 COGEP)', default=False, tracking=True)
    credit_bureau_authorized = fields.Boolean(string='Autoriza consulta de score en cualquier buró/plataforma autorizada', default=False, tracking=True)
    company_signature_stamp_acknowledged = fields.Boolean(string='Conoce requisito de firma y sello de CONEDERA', default=False, tracking=True)
    additional_financial_documents_accepted = fields.Boolean(string='Acepta entregar declaraciones IVA/renta y certificado bancario', default=False, tracking=True)
    declaration_date = fields.Datetime(string='Fecha de aceptación', readonly=True, copy=False)

    # Verificación interna de ubicación y negocio: estos campos solo se completan en Odoo.
    verification_province = fields.Char(string='Provincia de verificación')
    verification_city_canton_parish = fields.Char(string='Ciudad / cantón / parroquia')
    verification_neighborhood = fields.Char(string='Barrio')
    verification_address = fields.Char(string='Dirección verificada')
    verification_house_number = fields.Char(string='Número de casa')
    verification_reference = fields.Char(string='Referencia de ubicación')
    verification_sketch = fields.Binary(string='Croquis del cliente', attachment=True)
    verification_sketch_filename = fields.Char(string='Archivo del croquis')
    verification_zone = fields.Selection([('urban', 'Urbana'), ('peripheral', 'Periférica'), ('rural', 'Rural')], string='Zona')
    verification_local_state = fields.Selection([('very_good', 'Muy bueno'), ('good', 'Bueno'), ('regular', 'Regular'), ('bad', 'Malo')], string='Estado del local')
    interviewed_person = fields.Char(string='Persona entrevistada')
    interviewed_relationship = fields.Char(string='Relación / parentesco')
    inspection_done = fields.Selection([('yes', 'Sí'), ('no', 'No')], string='Se realizó la inspección')
    address_found = fields.Selection([('yes', 'Sí'), ('no', 'No')], string='Se encontró la dirección')
    client_lives_there = fields.Selection([('yes', 'Sí'), ('no', 'No')], string='El cliente vive en esa dirección')
    sketch_needed = fields.Selection([('yes', 'Sí'), ('no', 'No')], string='Necesita croquis')
    verifier_name = fields.Char(string='Nombre del verificador')
    verifier_signature = fields.Binary(string='Firma del verificador', attachment=True)
    verifier_signature_filename = fields.Char(string='Archivo de firma')

    _sql_constraints = [
        ('conedera_credit_application_name_uniq', 'unique(name)', 'El número de solicitud debe ser único.'),
    ]

    @api.model
    def _read_group_stage_ids(self, stages, domain, order=None):
        return self.env['conedera.credit.stage'].search([('active', '=', True)], order=order or 'sequence, id')

    @api.depends('document_ids.is_complete')
    def _compute_document_complete(self):
        for record in self:
            docs = record.document_ids[:1]
            record.document_complete = bool(docs and docs.is_complete)

    @api.model_create_multi
    def create(self, vals_list):
        Stage = self.env['conedera.credit.stage']
        for vals in vals_list:
            if vals.get('name', 'Nuevo') == 'Nuevo':
                vals['name'] = self.env['ir.sequence'].next_by_code('conedera.credit.application') or _('Nuevo')
            if not vals.get('stage_id'):
                initial = Stage.search([('is_initial', '=', True), ('active', '=', True)], order='sequence,id', limit=1)
                if not initial:
                    initial = Stage.search([('active', '=', True)], order='sequence,id', limit=1)
                if initial:
                    vals['stage_id'] = initial.id
            stage = Stage.browse(vals.get('stage_id')) if vals.get('stage_id') else Stage
            if stage and stage.is_approved:
                vals['documents_unlocked'] = True
            if vals.get('declaration_accepted'):
                vals['declaration_date'] = fields.Datetime.now()
        records = super().create(vals_list)
        for record in records:
            if record.stage_id:
                self.env['conedera.credit.stage.history'].sudo().create({
                    'application_id': record.id,
                    'stage_id': record.stage_id.id,
                    'user_id': self.env.user.id,
                    'notes': _('Solicitud registrada desde el portal'),
                    'visible_to_portal': True,
                })
            record.message_post(body=_('Solicitud registrada. Etapa inicial: %s') % escape(record.stage_id.name or ''))
        return records

    def write(self, vals):
        previous_stages = {record.id: record.stage_id for record in self} if 'stage_id' in vals else {}
        values = dict(vals)
        if 'stage_id' in values:
            new_stage = self.env['conedera.credit.stage'].browse(values.get('stage_id'))
            if new_stage.is_approved:
                values['documents_unlocked'] = True
            elif new_stage.is_rejected:
                values['documents_unlocked'] = False
        if values.get('declaration_accepted'):
            values.setdefault('declaration_date', fields.Datetime.now())
        result = super().write(values)
        if 'stage_id' in vals:
            for record in self:
                old_stage = previous_stages.get(record.id)
                if old_stage.id == record.stage_id.id:
                    continue
                self.env['conedera.credit.stage.history'].sudo().create({
                    'application_id': record.id,
                    'stage_id': record.stage_id.id,
                    'user_id': self.env.user.id,
                    'notes': _('Etapa actualizada de "%s" a "%s"') % (old_stage.name or '-', record.stage_id.name or '-'),
                    'visible_to_portal': True,
                })
                record.message_post(body=_('La solicitud cambió de etapa: <b>%s</b> → <b>%s</b>.') % (escape(old_stage.name or '-'), escape(record.stage_id.name or '-')))
                record._send_stage_notification(old_stage, record.stage_id)
        return result

    def _send_stage_notification(self, old_stage, new_stage):
        self.ensure_one()
        email = self.portal_user_id.email or self.portal_user_id.login
        if not email:
            return
        try:
            body = _(
                '<p>Estimado/a %(name)s:</p>'
                '<p>La solicitud de crédito <b>%(number)s</b> registra un cambio de etapa.</p>'
                '<p>Estado anterior: %(old)s<br/>Estado actual: <b>%(new)s</b></p>'
                '<p>Puede consultar el historial ingresando al portal de CONEDERA.</p>'
            ) % {
                'name': escape(self.applicant_name or self.portal_user_id.name or ''),
                'number': escape(self.name or ''),
                'old': escape(old_stage.name or '-'),
                'new': escape(new_stage.name or '-'),
            }
            mail = self.env['mail.mail'].sudo().create({
                'subject': _('Actualización de solicitud de crédito %s') % self.name,
                'body_html': body,
                'email_to': email,
                'email_from': self.env.company.email or self.env['ir.config_parameter'].sudo().get_param('mail.default.from') or False,
            })
            mail.send()
        except Exception:
            _logger.exception('No se pudo notificar por correo la etapa de solicitud %s', self.name)

    def action_mark_documentation_received(self):
        for record in self:
            stage = self.env['conedera.credit.stage'].search([('name', '=', 'Documentación recibida')], limit=1)
            if stage:
                record.stage_id = stage

    def action_open_portal(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_url',
            'url': '/my/credito/%s' % self.id,
            'target': 'new',
        }

    @api.constrains('dependents_count', 'monthly_sales', 'social_capital', 'assets_amount', 'monthly_income', 'liabilities_amount', 'monthly_expenses', 'vehicle1_value', 'vehicle2_value', 'employment_salary')
    def _check_non_negative_amounts(self):
        for record in self:
            if record.dependents_count < 0:
                raise ValidationError(_('El número de cargas no puede ser negativo.'))
            for field_name in ('monthly_sales', 'social_capital', 'assets_amount', 'monthly_income', 'liabilities_amount', 'monthly_expenses', 'vehicle1_value', 'vehicle2_value', 'employment_salary'):
                if record[field_name] < 0:
                    raise ValidationError(_('Los montos de la solicitud no pueden ser negativos.'))
