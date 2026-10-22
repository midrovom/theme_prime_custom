import base64
import logging

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class ConederaCreditDocuments(models.Model):
    _name = 'conedera.credit.documents'
    _description = 'Documentación solicitada para crédito CONEDERA'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc, id desc'

    application_id = fields.Many2one(
        'conedera.credit.application', string='Solicitud de crédito', required=True,
        ondelete='cascade', index=True, tracking=True,
    )
    person_type = fields.Selection(related='application_id.person_type', string='Tipo de solicitante', store=True, readonly=True)
    applicant_name = fields.Char(related='application_id.applicant_name', string='Solicitante', store=True, readonly=True)
    state = fields.Selection([
        ('pending', 'Pendiente de carga'),
        ('submitted', 'En revisión'),
        ('accepted', 'Aceptada'),
        ('correction', 'Requiere correcciones'),
    ], string='Estado documental', default='pending', required=True, tracking=True)
    review_notes = fields.Text(string='Observaciones de revisión')

    application_signed = fields.Binary(string='Solicitud de crédito preparada y firmada', attachment=True)
    application_signed_filename = fields.Char(string='Archivo - solicitud firmada')
    ruc_updated = fields.Binary(string='Copia del RUC actualizado', attachment=True)
    ruc_updated_filename = fields.Char(string='Archivo - RUC actualizado')

    id_client = fields.Binary(string='Cédula a color del cliente', attachment=True)
    id_client_filename = fields.Char(string='Archivo - cédula del cliente')
    id_spouse = fields.Binary(string='Cédula a color del cónyuge (si corresponde)', attachment=True)
    id_spouse_filename = fields.Char(string='Archivo - cédula del cónyuge')
    voting_certificate = fields.Binary(string='Certificado de votación vigente del cliente', attachment=True)
    voting_certificate_filename = fields.Char(string='Archivo - votación del cliente')

    id_legal_representative = fields.Binary(string='Cédula a color del representante legal', attachment=True)
    id_legal_representative_filename = fields.Char(string='Archivo - cédula del representante legal')
    voting_legal_representative = fields.Binary(string='Certificado de votación vigente del representante legal', attachment=True)
    voting_legal_representative_filename = fields.Char(string='Archivo - votación del representante legal')
    legal_appointment = fields.Binary(string='Nombramiento del representante legal', attachment=True)
    legal_appointment_filename = fields.Char(string='Archivo - nombramiento del representante legal')

    utility_business = fields.Binary(string='Planilla de servicio básico del local', attachment=True)
    utility_business_filename = fields.Char(string='Archivo - planilla del local')
    utility_residence = fields.Binary(string='Planilla de servicio básico del lugar de residencia', attachment=True)
    utility_residence_filename = fields.Char(string='Archivo - planilla de residencia')
    local_photo_inside = fields.Binary(string='Fotografía de la parte interna del local', attachment=True)
    local_photo_inside_filename = fields.Char(string='Archivo - fotografía interna del local')
    local_photo_outside = fields.Binary(string='Fotografía de la parte externa del local', attachment=True)
    local_photo_outside_filename = fields.Char(string='Archivo - fotografía externa del local')
    applicant_signing_photo = fields.Binary(string='Fotografía del solicitante firmando, con el rostro claramente visible', attachment=True)
    applicant_signing_photo_filename = fields.Char(string='Archivo - fotografía del solicitante firmando')
    vat_declarations = fields.Binary(string='Últimas 6 declaraciones del IVA (archivo consolidado)', attachment=True)
    vat_declarations_filename = fields.Char(string='Archivo - declaraciones del IVA')
    income_tax_return = fields.Binary(string='Declaración del Impuesto a la Renta del año anterior', attachment=True)
    income_tax_return_filename = fields.Char(string='Archivo - Impuesto a la Renta')
    bank_certificate = fields.Binary(string='Certificado bancario correspondiente a los últimos 6 meses', attachment=True)
    bank_certificate_filename = fields.Char(string='Archivo - certificado bancario')

    is_complete = fields.Boolean(string='Documentación completa', compute='_compute_summary', store=True)
    required_document_total = fields.Integer(string='Documentos requeridos', compute='_compute_summary', store=True)
    required_document_uploaded = fields.Integer(string='Documentos cargados', compute='_compute_summary', store=True)
    required_document_missing = fields.Integer(string='Documentos faltantes', compute='_compute_summary', store=True)
    last_portal_upload = fields.Datetime(string='Última carga del portal', readonly=True)

    _sql_constraints = [
        ('conedera_credit_documents_application_unique', 'unique(application_id)', 'Solo puede existir un expediente documental por solicitud.'),
    ]

    def _required_fields(self):
        self.ensure_one()
        common = [
            'application_signed', 'ruc_updated', 'utility_business', 'utility_residence',
            'local_photo_inside', 'local_photo_outside', 'applicant_signing_photo',
            'vat_declarations', 'income_tax_return', 'bank_certificate',
        ]
        if self.application_id.person_type == 'juridical':
            return common + ['id_legal_representative', 'voting_legal_representative', 'legal_appointment']
        natural = common + ['id_client', 'voting_certificate']
        if self.application_id.spouse_name:
            natural.append('id_spouse')
        return natural

    @api.depends(
        'application_id.person_type', 'application_id.spouse_name',
        'application_signed', 'ruc_updated', 'id_client', 'id_spouse',
        'voting_certificate', 'id_legal_representative', 'voting_legal_representative',
        'legal_appointment', 'utility_business', 'utility_residence',
        'local_photo_inside', 'local_photo_outside', 'applicant_signing_photo',
        'vat_declarations', 'income_tax_return', 'bank_certificate',
    )
    def _compute_summary(self):
        for record in self:
            required = record._required_fields()
            uploaded = sum(bool(record[field_name]) for field_name in required)
            record.required_document_total = len(required)
            record.required_document_uploaded = uploaded
            record.required_document_missing = len(required) - uploaded
            record.is_complete = bool(required) and uploaded == len(required)

    def _check_files(self, values):
        allowed_image = ('.jpg', '.jpeg', '.png')
        allowed_document = ('.pdf', '.jpg', '.jpeg', '.png')
        for field_name, content in values.items():
            if not field_name.endswith('_filename') or not content:
                continue
            binary_field = field_name[:-9]
            if binary_field not in self._fields or self._fields[binary_field].type != 'binary':
                continue
            filename = str(content).lower().strip()
            allowed = allowed_image if binary_field in {'local_photo_inside', 'local_photo_outside', 'applicant_signing_photo'} else allowed_document
            if not filename.endswith(allowed):
                raise ValidationError(_('El archivo "%s" tiene un formato no permitido.') % self._fields[field_name].string)

        for field_name, content in values.items():
            if field_name not in self._fields or self._fields[field_name].type != 'binary' or not content:
                continue
            filename = (values.get('%s_filename' % field_name) or '').lower()
            if not filename:
                continue
            try:
                raw = base64.b64decode(content)
            except Exception:
                raise ValidationError(_('No se pudo leer el archivo "%s".') % self._fields[field_name].string)
            valid = True
            if filename.endswith('.pdf'):
                valid = raw.startswith(b'%PDF')
            elif filename.endswith(('.jpg', '.jpeg')):
                valid = raw.startswith(b'\xff\xd8\xff')
            elif filename.endswith('.png'):
                valid = raw.startswith(b'\x89PNG\r\n\x1a\n')
            if not valid:
                raise ValidationError(_('El contenido del archivo "%s" no coincide con su extensión.') % (values.get('%s_filename' % field_name) or field_name))

    @api.model_create_multi
    def create(self, vals_list):
        for values in vals_list:
            self._check_files(values)
        return super().create(vals_list)

    def write(self, vals):
        self._check_files(vals)
        return super().write(vals)

    def action_mark_submitted(self):
        for record in self:
            record.state = 'submitted'
            record.message_post(body=_('El solicitante cargó documentación para revisión.'))

    def action_mark_accepted(self):
        for record in self:
            if not record.is_complete:
                raise ValidationError(_('No se puede aceptar un expediente con documentos pendientes.'))
            record.state = 'accepted'
            record.message_post(body=_('La documentación fue marcada como aceptada.'))

    def action_request_correction(self):
        for record in self:
            record.state = 'correction'
            record.message_post(body=_('Se solicitaron correcciones en la documentación.'))
