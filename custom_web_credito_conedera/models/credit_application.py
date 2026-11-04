import base64
import binascii
import logging
from markupsafe import escape

import re
import zlib
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, AccessError, UserError

from .credit_identity import valid_ecuador_mobile, valid_credit_identity, valid_ecuador_or_foreign_document, valid_ruc_length

_logger = logging.getLogger(__name__)

# Mantiene las claves existentes en la base de datos; las combinaciones nuevas
# permiten conceder por solicitud cada formulario de manera independiente.
PORTAL_SCOPE_SECTIONS = {
    'none': frozenset(),
    'history': frozenset({'history'}),
    'documentation': frozenset({'documentation'}),
    'both': frozenset({'history', 'documentation'}),
    'sketch': frozenset({'sketch'}),
    'history_sketch': frozenset({'history', 'sketch'}),
    'documentation_sketch': frozenset({'documentation', 'sketch'}),
    'all': frozenset({'history', 'documentation', 'sketch'}),
}



class ConederaCreditApplication(models.Model):
    _name = 'conedera.credit.application'
    _description = 'Solicitud de crédito CONEDERA S.A.'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc, id desc'

    website_id = fields.Many2one('website', string='Sitio web de origen', readonly=True, copy=False, index=True,
        help='Dominio donde se registró la solicitud. La empresa sigue siendo company_id.')
    company_id = fields.Many2one(
        'res.company', string='Empresa', required=True, index=True, tracking=True,
        default=lambda self: self.env.company,
        help='Empresa propietaria de la solicitud. Controla el acceso y los datos impresos en PDF.')
    @api.constrains('website_id', 'company_id')
    def _check_website_company_consistency(self):
        for application in self:
            if (application.website_id and application.website_id.company_id and
                    application.website_id.company_id != application.company_id):
                raise ValidationError(_('La empresa de la solicitud debe coincidir con la del sitio web de origen.'))

    @api.constrains('company_id')
    def _check_company_assignment(self):
        # Users with internal access may only associate records with an
        # authorized company. Portal registration uses an Odoo-controlled value.
        if not self.env.su:
            allowed_ids = set(self.env.companies.ids)
            for application in self:
                if application.company_id.id not in allowed_ids:
                    raise AccessError(_('La empresa de esta solicitud no está entre sus empresas autorizadas.'))

    name = fields.Char(string='Número de solicitud', required=True, copy=False, readonly=True, default='Nuevo', tracking=True, index=True)
    active = fields.Boolean(default=True)
    # Puede existir una solicitud creada desde el backend sin usuario de portal.
    # Los accesos web siguen autorizándose SOLO por portal_user_id.
    portal_user_id = fields.Many2one('res.users', string='Usuario del portal', readonly=True, index=True, ondelete='restrict')
    partner_id = fields.Many2one(
        'res.partner', string='Contacto solicitante', index=True, tracking=True, ondelete='restrict',
        help='Contacto comercial al cual pertenece este expediente de crédito. '
             'En solicitudes del portal se identifica o crea automáticamente. '
             'En solicitudes internas se selecciona desde Contactos.')
    credit_origin = fields.Selection(
        [('portal', 'Portal web'), ('backend', 'Registro interno')],
        string='Origen', default='backend', required=True, readonly=True, copy=False, index=True)

    # Campo antiguo conservado exclusivamente para migrar solicitudes históricas.
    # No participa en las nuevas solicitudes ni condiciona los documentos.
    person_type = fields.Selection([
        ('natural', 'Persona natural'), ('juridical', 'Persona jurídica'),
    ], string='Tipo anterior (histórico)', readonly=True, copy=False)
    applicant_type_id = fields.Many2one(
        'conedera.credit.applicant.type', string='Tipo de solicitante',
        tracking=True, index=True, ondelete='restrict',
        help='Catálogo editable en Crédito CONEDERA > Tipos de solicitante.')
    application_place = fields.Char(string='Lugar de solicitud')
    identification = fields.Char(string='Documento del solicitante', required=True, tracking=True, index=True)
    identification_type = fields.Selection([('cedula', 'Cédula ecuatoriana'), ('ruc', 'RUC'), ('foreign', 'Cédula extranjera')], string='Tipo de documento', default='cedula', required=True, tracking=True)
    application_date = fields.Date(string='Lugar y fecha de solicitud', required=True, default=fields.Date.context_today)
    # A partir de 18.0.1.8.49 el campo técnico applicant_name ES un res.partner.
    # partner_id mantiene la vinculación histórica y el smart button de Contactos.
    # Ambos representan exactamente el mismo contacto, nunca dos solicitantes.
    applicant_name = fields.Many2one(
        'res.partner', string='Solicitante', related='partner_id', store=True,
        readonly=False, tracking=True,
        help='Seleccione el contacto existente de Odoo que presenta la solicitud.')
    # Nombre capturado al llenar la ficha. Se conserva intacto para PDF,
    # correcciones e historial; en personas jurídicas puede ser el representante,
    # mientras que applicant_name/partner_id señalan al cliente (empresa).
    applicant_name_text = fields.Char(
        string='Nombre declarado en la ficha', copy=True,
        help='Texto original del propietario o representante para conservar el histórico.')
    applicant_email = fields.Char(string='Correo electrónico del propietario o representante', required=True)
    phone_fixed = fields.Char(string='Teléfono fijo')
    mobile = fields.Char(string='Celular', required=True)
    profession = fields.Char(string='Profesión')
    # Conservado como dato histórico; los nuevos registros utilizan el catálogo editable.
    marital_status = fields.Selection([
        ('single', 'Soltero/a'), ('married', 'Casado/a'), ('divorced', 'Divorciado/a'),
        ('widowed', 'Viudo/a'), ('free_union', 'Unión de hecho'), ('other', 'Otro'),
    ], string='Estado civil (anterior)', copy=False, readonly=True)
    marital_status_id = fields.Many2one(
        'conedera.credit.marital.status', string='Estado civil', ondelete='restrict', index=True,
        help='Estados civiles configurables en Crédito CONEDERA > Estados civiles.')
    foreign_residence_time = fields.Char(string='Tiempo de residencia (extranjero)')
    foreign_work_visa = fields.Selection([('yes', 'Sí'), ('no', 'No')], string='Visa de trabajo (extranjero)')
    spouse_name = fields.Char(string='Nombres y apellidos del cónyuge')
    spouse_identification = fields.Char(string='Cédula del cónyuge')
    spouse_profession = fields.Char(string='Profesión del cónyuge')
    dependents_count = fields.Integer(string='Número de cargas')
    home_address = fields.Char(string='Dirección domiciliaria')
    # Compatibilidad con las solicitudes anteriores. Nuevas solicitudes usan el catálogo.
    housing_type = fields.Selection([
        ('own', 'Propia'), ('rented', 'Alquilada'), ('family', 'Familiares'), ('mortgaged', 'Hipotecada'),
    ], string='Vivienda (anterior)', readonly=True, copy=False)
    housing_type_id = fields.Many2one(
        'conedera.credit.housing.type', string='Vivienda', index=True, ondelete='restrict',
        help='Opciones configurables desde Crédito CONEDERA > Tipos de vivienda.')
    vehicle_ids = fields.One2many('conedera.credit.vehicle', 'application_id', string='Vehículos del solicitante')
    legacy_vehicle_migrated = fields.Boolean(string='Vehículos históricos migrados', default=False, copy=False)

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
    business_location_captured = fields.Char(string='Ubicación capturada automáticamente', copy=False, readonly=True, help='Coordenadas declaradas por el navegador cuando el cliente usa la captura automática. No constituye certificación de GPS.')
    business_location_method = fields.Selection([('automatic', 'Ubicación actual'), ('manual', 'Coordenadas ingresadas manualmente')], string='Método de ubicación', default='manual', copy=False, readonly=True)
    business_latitude = fields.Float(string='Latitud del negocio', digits=(10, 7))
    business_longitude = fields.Float(string='Longitud del negocio', digits=(10, 7))
    # Compatibilidad temporal con vistas almacenadas de versiones anteriores.
    # No se muestra en el portal, no se solicita y no se utiliza para ubicación.
    maps_url = fields.Char(string='Enlace histórico de ubicación (en desuso)', readonly=True, copy=False)


    employment_relationship = fields.Selection([('yes', 'Sí'), ('no', 'No')], string='¿Tiene relación de dependencia?')
    employment_employer_type = fields.Selection([('private', 'Privado'), ('public', 'Público')], string='Tipo de empleador (histórico)', readonly=True, copy=False)
    employment_employer_type_id = fields.Many2one(
        'conedera.credit.employer.type', string='Tipo de empleador', ondelete='restrict', index=True,
        help='Opción configurable desde Crédito CONEDERA > Configuración > Tipos de empleador.')
    employment_company = fields.Char(string='Empresa donde trabaja (relación de dependencia)')
    employment_activity = fields.Char(string='Actividad de la empresa')
    employment_address = fields.Char(string='Dirección de la empresa donde trabaja')
    employment_phone = fields.Char(string='Teléfono de empresa donde trabaja')
    employment_start_date = fields.Date(string='Fecha de ingreso al empleo')
    employment_position = fields.Char(string='Cargo')
    employment_salary = fields.Monetary(string='Sueldo', currency_field='currency_id')

    reference_ids = fields.One2many('conedera.credit.reference', 'application_id', string='Referencias')
    # Las tres vistas administrativas se filtran por tipo; el campo general se
    # conserva para el portal, los reportes y las solicitudes ya existentes.
    commercial_reference_ids = fields.One2many(
        'conedera.credit.reference', 'application_id',
        string='Referencias comerciales', domain=[('reference_type', '=', 'commercial')],
    )
    personal_reference_ids = fields.One2many(
        'conedera.credit.reference', 'application_id',
        string='Referencias personales', domain=[('reference_type', '=', 'personal')],
    )
    bank_reference_ids = fields.One2many(
        'conedera.credit.reference', 'application_id',
        string='Referencias bancarias', domain=[('reference_type', '=', 'bank')],
    )
    history_ids = fields.One2many('conedera.credit.stage.history', 'application_id', string='Historial de etapas', readonly=True)
    document_ids = fields.One2many('conedera.credit.documents', 'application_id', string='Documentos solicitados', copy=False)
    document_complete = fields.Boolean(string='Documentación completa', compute='_compute_document_complete')

    # PDFs ya firmados que carga CONEDERA. No son los reportes QWeb originales.
    # El almacenamiento attachment=True respeta la base de datos/filestore de Odoo.
    signed_application_pdf = fields.Binary(
        string='Solicitud de crédito firmada (PDF)', attachment=True, copy=False)
    signed_application_filename = fields.Char(
        string='Nombre de la solicitud firmada', copy=False)
    signed_verification_pdf = fields.Binary(
        string='Verificación de ubicación firmada (PDF)', attachment=True, copy=False)
    signed_verification_filename = fields.Char(
        string='Nombre de la verificación firmada', copy=False)
    # Archivos firmados múltiples, agrupados por tipo y vinculados al expediente.
    # many2many_binary permite seleccionar/arrastrar varios PDFs en el backend.
    signed_application_attachment_ids = fields.Many2many(
        'ir.attachment', 'conedera_credit_signed_application_rel',
        'application_id', 'attachment_id', string='Solicitudes firmadas (PDF)', copy=False)
    signed_verification_attachment_ids = fields.Many2many(
        'ir.attachment', 'conedera_credit_signed_verification_rel',
        'application_id', 'attachment_id', string='Verificaciones firmadas (PDF)', copy=False)
    signed_application_available = fields.Boolean(
        string='Solicitud firmada disponible', compute='_compute_signed_pdf_available', store=True)
    signed_verification_available = fields.Boolean(
        string='Verificación firmada disponible', compute='_compute_signed_pdf_available', store=True)

    @api.depends('signed_application_pdf', 'signed_verification_pdf',
                 'signed_application_attachment_ids', 'signed_verification_attachment_ids')
    def _compute_signed_pdf_available(self):
        for application in self:
            application.signed_application_available = bool(
                application.signed_application_attachment_ids or application.signed_application_pdf)
            application.signed_verification_available = bool(
                application.signed_verification_attachment_ids or application.signed_verification_pdf)

    @api.constrains('signed_application_attachment_ids', 'signed_verification_attachment_ids')
    def _check_signed_pdf_attachments(self):
        """Validación real en el servidor: formato, peso y asociación segura.

        No confiar en accepted_file_extensions (solo afecta al selector web).
        """
        for application in self:
            for category in ('signed_application_attachment_ids', 'signed_verification_attachment_ids'):
                for attachment in application[category]:
                    filename = (attachment.name or '').strip()
                    if not filename.lower().endswith('.pdf') or attachment.type != 'binary':
                        raise ValidationError(_('Los documentos firmados deben ser archivos PDF.'))
                    if attachment.file_size > 25 * 1024 * 1024:
                        raise ValidationError(_('El documento firmado "%s" supera 25 MB.') % filename)
                    if attachment.res_model == self._name and attachment.res_id not in (False, application.id):
                        raise ValidationError(_('El archivo "%s" ya está vinculado a otra solicitud.') % filename)
                    try:
                        pdf = base64.b64decode(attachment.datas or b'', validate=True)
                    except (ValueError, TypeError, binascii.Error):
                        raise ValidationError(_('No se pudo comprobar el PDF "%s".') % filename)
                    if not pdf.startswith(b'%PDF-') or len(pdf) > 25 * 1024 * 1024:
                        raise ValidationError(_('El documento "%s" no es un PDF válido de hasta 25 MB.') % filename)

    @api.model
    def _migrate_credit_signed_documents(self):
        """Agregar los archivos firmados antiguos a la lista sin perder originales.

        Se puede ejecutar varias veces con seguridad al actualizar el módulo.
        """
        Application = self.sudo().with_context(active_test=False)
        Attachment = self.env['ir.attachment'].sudo()
        for application in Application.search([]):
            for old_data, old_name, relation, fallback in (
                ('signed_application_pdf', 'signed_application_filename',
                 'signed_application_attachment_ids', 'Solicitud_Firmada.pdf'),
                ('signed_verification_pdf', 'signed_verification_filename',
                 'signed_verification_attachment_ids', 'Verificacion_Firmada.pdf'),
            ):
                if not application[old_data]:
                    continue
                name = (application[old_name] or fallback).strip()
                if not name.lower().endswith('.pdf'):
                    name += '.pdf'
                payload = application[old_data]
                if not any(att.name == name and base64.b64decode(att.datas or b'') == base64.b64decode(payload)
                           for att in application[relation]):
                    attachment = Attachment.create({
                        'name': name, 'type': 'binary', 'datas': payload,
                        'mimetype': 'application/pdf', 'res_model': self._name,
                        'res_id': application.id, 'public': False,
                    })
                    application.write({relation: [(4, attachment.id)]})
        return True

    @api.constrains('signed_application_pdf', 'signed_application_filename',
                    'signed_verification_pdf', 'signed_verification_filename')
    def _check_signed_pdfs(self):
        """Aceptar exclusivamente PDFs originales, con límite de 25 MB por archivo."""
        for application in self:
            for data_field, name_field, label in (
                ('signed_application_pdf', 'signed_application_filename', 'solicitud firmada'),
                ('signed_verification_pdf', 'signed_verification_filename', 'verificación firmada'),
            ):
                payload = application[data_field]
                if not payload:
                    continue
                filename = (application[name_field] or '').strip()
                if not filename.lower().endswith('.pdf'):
                    raise ValidationError(_('El archivo de %s debe tener extensión .pdf.') % label)
                try:
                    raw = base64.b64decode(payload, validate=True)
                except (ValueError, TypeError, binascii.Error):
                    raise ValidationError(_('El archivo de %s no contiene un PDF válido.') % label)
                if not raw.startswith(b'%PDF-'):
                    raise ValidationError(_('El archivo de %s debe ser un PDF real.') % label)
                if len(raw) > 25 * 1024 * 1024:
                    raise ValidationError(_('El PDF de %s supera el límite de 25 MB.') % label)

    stage_id = fields.Many2one(
        'conedera.credit.stage', string='Etapa', tracking=True, index=True,
        group_expand='_read_group_stage_ids', ondelete='restrict',
        default=lambda self: self.env['conedera.credit.stage'].search([('is_initial', '=', True)], order='sequence,id', limit=1),
    )
    verification_status = fields.Selection([('pending', 'Pendiente'), ('in_progress', 'En verificación'), ('verified', 'Verificado'), ('failed', 'No conforme')], string='Estado de verificación del negocio', default='pending', required=True, tracking=True, copy=False, index=True, help='Se gestiona en paralelo con la etapa de revisión del crédito.')
    verification_completed_at = fields.Datetime(string='Fecha de verificación', readonly=True, copy=False)
    documents_unlocked = fields.Boolean(string='Ingreso documental habilitado', default=False, copy=False, readonly=True, tracking=True)
    document_access_allowed = fields.Boolean(
        string='Puede ingresar documentos', compute='_compute_document_access_allowed',
        help='Solo está disponible tras aprobar la solicitud, mientras siga aprobada o esté en la fase de recepción documental.')
    currency_id = fields.Many2one('res.currency', string='Moneda', default=lambda self: self.env.company.currency_id, required=True)
    declaration_accepted = fields.Boolean(string='Declaración y autorización general aceptada', required=True, default=False, tracking=True)
    prior_commercial_relationship_accepted = fields.Boolean(string='Acepta cláusula de relación comercial previa', default=False, tracking=True)
    electronic_service_accepted = fields.Boolean(string='Acepta citación telemática (Art. 55.1 COGEP)', default=False, tracking=True)
    credit_bureau_authorized = fields.Boolean(string='Autoriza consulta de score en cualquier buró/plataforma autorizada', default=False, tracking=True)
    company_signature_stamp_acknowledged = fields.Boolean(string='Conoce requisito de firma y sello de CONEDERA', default=False, tracking=True)
    additional_financial_documents_accepted = fields.Boolean(string='Acepta entregar declaraciones IVA/renta y certificado bancario', default=False, tracking=True)
    declaration_date = fields.Datetime(string='Fecha de aceptación', readonly=True, copy=False)

    # Verificación interna de ubicación y negocio: estos campos solo se completan en Odoo.
    verification_province = fields.Char(string='Provincia indicada por el cliente')
    verification_city_canton_parish = fields.Char(string='Ciudad / cantón / parroquia (histórico)')
    verification_city = fields.Char(string='Ciudad indicada por el cliente')
    verification_canton = fields.Char(string='Cantón indicado por el cliente')
    verification_parish = fields.Char(string='Parroquia indicada por el cliente')
    verification_neighborhood = fields.Char(string='Barrio')
    verification_address = fields.Char(string='Dirección indicada por el cliente')
    verification_house_number = fields.Char(string='Número de casa')
    verification_reference = fields.Char(string='Referencia de ubicación')
    verification_sketch = fields.Binary(string='Croquis del cliente', attachment=True)
    verification_sketch_filename = fields.Char(string='Archivo del croquis')
    @api.constrains('verification_sketch', 'verification_sketch_filename')
    def _check_sketch_is_image(self):
        """New croquis uploads must be valid images; historical PDFs remain readable."""
        for record in self:
            if not record.verification_sketch:
                continue
            filename = (record.verification_sketch_filename or '').lower().strip()
            ext = filename.rsplit('.', 1)[-1] if '.' in filename else ''
            if ext not in ('png', 'jpg', 'jpeg', 'webp'):
                raise ValidationError(_('El croquis solo admite imágenes PNG, JPG o WEBP.'))
            try:
                raw = base64.b64decode(record.verification_sketch, validate=True)
            except (ValueError, binascii.Error, TypeError):
                raise ValidationError(_('El archivo del croquis no es una imagen válida.'))
            signatures = {
                'png': raw.startswith(b'\x89PNG\r\n\x1a\n'),
                'jpg': raw.startswith(b'\xff\xd8\xff'),
                'jpeg': raw.startswith(b'\xff\xd8\xff'),
                'webp': raw.startswith(b'RIFF') and raw[8:12] == b'WEBP',
            }
            if not signatures.get(ext) or not raw or len(raw) > 12 * 1024 * 1024:
                raise ValidationError(_('El croquis debe ser una imagen PNG, JPG o WEBP de hasta 12 MB.'))

    # Conservados solo para migrar la información antigua. Ya no se usan en las vistas.
    verification_zone = fields.Selection([
        ('urban', 'Urbana'), ('peripheral', 'Periférica'), ('rural', 'Rural'),
    ], string='Zona (histórico)', readonly=True, copy=False)
    verification_local_state = fields.Selection([
        ('very_good', 'Muy bueno'), ('good', 'Bueno'), ('regular', 'Regular'), ('bad', 'Malo'),
    ], string='Estado del local (histórico)', readonly=True, copy=False)
    verification_zone_id = fields.Many2one(
        'conedera.credit.verification.zone', string='Zona', index=True, ondelete='restrict')
    verification_local_state_id = fields.Many2one(
        'conedera.credit.local.condition', string='Estado del local', index=True, ondelete='restrict')
    # Campo legado conservado exclusivamente por compatibilidad con registros históricos; no se expone.
    interviewed_person = fields.Char(string='Persona entrevistada (histórico)', readonly=True, copy=False)
    interviewed_relationship = fields.Char(string='Relación / parentesco')
    interviewed_name = fields.Char(string='Nombre')
    inspection_done = fields.Selection([('yes', 'Sí'), ('no', 'No')], string='Se realizó la inspección')
    address_found = fields.Selection([('yes', 'Sí'), ('no', 'No')], string='Se encontró la dirección')
    client_lives_there = fields.Selection([('yes', 'Sí'), ('no', 'No')], string='El cliente vive en esa dirección')
    sketch_needed = fields.Selection([('yes', 'Sí'), ('no', 'No')], string='Necesita croquis')
    verifier_name = fields.Char(string='Nombre del verificador')
    verifier_signature = fields.Binary(string='Firma del verificador', attachment=True)
    verifier_signature_filename = fields.Char(string='Archivo de firma')
    credit_verification_final_required = fields.Boolean(
        compute='_compute_credit_verification_final_required',
        string='Verificación final obligatoria')

    @api.depends('stage_id.is_approved', 'stage_id.is_rejected', 'verification_status')
    def _compute_credit_verification_final_required(self):
        for record in self:
            record.credit_verification_final_required = bool(
                (record.stage_id and (record.stage_id.is_approved or record.stage_id.is_rejected))
                or record.verification_status in ('verified', 'failed')
            )

    client_submission_uuid = fields.Char(string='Identificador de envío del portal', copy=False, readonly=True, index=True)

    _sql_constraints = [
        ('conedera_credit_client_submission_uuid_uniq', 'unique(client_submission_uuid)', 'Esta solicitud ya fue enviada desde este dispositivo.'),
        ('conedera_credit_application_company_name_uniq', 'unique(company_id, name)', 'El número de solicitud debe ser único dentro de la misma empresa.'),
    ]

    def _credit_report_sketch_image(self):
        """Imagen base64 del croquis, para incrustarla en el PDF QWeb.

        Si el cliente cargó un PDF, se convierte únicamente la primera página.
        La conversión es opcional: no puede bloquear la impresión del reporte.
        """
        self.ensure_one()
        if not self.verification_sketch:
            return False
        import base64
        import os
        import shutil
        import subprocess
        import tempfile

        filename = (self.verification_sketch_filename or '').lower()
        if filename.endswith(('.png', '.jpg', '.jpeg', '.webp')):
            return self.verification_sketch
        if not filename.endswith('.pdf'):
            return False
        try:
            pdf_bytes = base64.b64decode(self.verification_sketch)
            if len(pdf_bytes) > 12 * 1024 * 1024 or not pdf_bytes.startswith(b'%PDF-'):
                return False
            # PyMuPDF, si se encuentra instalado en el entorno Odoo.
            try:
                import fitz
            except ImportError:
                fitz = None
            if fitz:
                with fitz.open(stream=pdf_bytes, filetype='pdf') as doc:
                    if not doc.page_count:
                        return False
                    page = doc.load_page(0)
                    # 96 dpi; limita tiempo y memoria en croquis de gran tamaño.
                    scale = min(1.3333, 1300.0 / max(page.rect.width, page.rect.height))
                    raster = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
                    return base64.b64encode(raster.tobytes('png'))
            # Alternativa del sistema para instalaciones con Poppler.
            if shutil.which('pdftoppm'):
                with tempfile.TemporaryDirectory(prefix='conedera_sketch_') as tmpdir:
                    pdf_file = os.path.join(tmpdir, 'croquis.pdf')
                    with open(pdf_file, 'wb') as dst:
                        dst.write(pdf_bytes)
                    subprocess.run(
                        ['pdftoppm', '-f', '1', '-l', '1', '-singlefile', '-scale-to', '1300',
                         '-png', pdf_file, os.path.join(tmpdir, 'croquis')],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                        check=True, timeout=15,
                    )
                    with open(os.path.join(tmpdir, 'croquis.png'), 'rb') as src:
                        return base64.b64encode(src.read())
        except Exception:
            _logger.warning('No fue posible previsualizar el PDF de croquis de la solicitud %s', self.id, exc_info=True)
        return False

    def action_print_credit_application(self):
        """Seleccionar la sección del PDF sin alterar la solicitud."""
        return self.action_open_credit_print_wizard()

    def action_open_credit_print_wizard(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Descargar documentos de crédito'),
            'res_model': 'conedera.credit.print.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_application_id': self.id,
                'default_report_choice': 'both',
            },
        }

    # Indicador de permiso de edición SOLO para la vista del backend.
    # En registros aún sin guardar Odoo lee default_get() antes de realizar el
    # cálculo del booleano; devolver su valor evita bloquear el formulario Nuevo.
    credit_is_admin = fields.Boolean(
        compute='_compute_credit_is_admin', string='Edición completa habilitada')

    def _has_credit_admin_access(self):
        """Misma fuente de verdad para el formulario y el control ORM."""
        return bool(self.env.su or self.env.user.has_group(
            'custom_web_credito_conedera.group_credit_administrator'))

    @api.model
    def default_get(self, fields_list):
        defaults = super().default_get(fields_list)
        # Los campos computados no siempre tienen valor en una ficha nueva.
        # El widget utiliza este booleano para evaluar las expresiones readonly.
        if 'credit_is_admin' in fields_list:
            defaults['credit_is_admin'] = self._has_credit_admin_access()
        return defaults

    @api.depends_context('uid')
    def _compute_credit_is_admin(self):
        permitted = self._has_credit_admin_access()
        for application in self:
            application.credit_is_admin = permitted

    # El usuario de crédito SOLO puede cambiar la etapa y los campos de verificación
    # del negocio. Protegido en ORM además de en las vistas (RPC/importaciones).
    _credit_reviewer_writable = frozenset({
        'stage_id', 'verification_status', 'verification_completed_at',
        'verification_zone_id', 'verification_local_state_id',
        'interviewed_relationship', 'interviewed_name',
        'inspection_done', 'address_found', 'client_lives_there',
        'sketch_needed', 'verifier_name', 'verifier_signature',
        'verifier_signature_filename',
    })

    def _check_reviewer_values(self, values):
        if self._has_credit_admin_access():
            return
        if self.env.user.has_group('custom_web_credito_conedera.group_credit_manager'):
            forbidden = set(values).difference(self._credit_reviewer_writable)
            if forbidden:
                raise AccessError(_('El usuario de crédito solo puede cambiar la etapa y completar la verificación del negocio. Campos no autorizados: %s') % ', '.join(sorted(forbidden)))

    @api.model
    def _read_group_stage_ids(self, stages, domain, order=None):
        return self.env['conedera.credit.stage'].search([('active', '=', True)], order=order or 'sequence, id')

    @api.depends('document_ids.is_complete', 'document_ids.document_line_ids.file')
    def _compute_document_complete(self):
        for record in self:
            docs = record.document_ids[:1]
            record.document_complete = bool(docs and docs.is_complete)

    # Permiso POR SOLICITUD como custom_web_hr_historial_postulaciones.
    # El grupo del usuario no autoriza a modificar expedientes ajenos o sin habilitar.
    portal_history_consumed_at = fields.Datetime(string='Última corrección autorizada del portal', readonly=True, copy=False)
    portal_sketch_consumed_at = fields.Datetime(string='Última corrección autorizada del croquis', readonly=True, copy=False)
    portal_update_scope = fields.Selection([
        ('none', 'Ninguna sección'),
        ('history', 'Historial de solicitudes (actualizar formulario)'),
        ('documentation', 'Ingreso de documentos (actualizar archivos)'),
        ('both', 'Historial + documentación'),
        ('sketch', 'Croquis del cliente'),
        ('history_sketch', 'Solicitud + croquis'),
        ('documentation_sketch', 'Documentación + croquis'),
        ('all', 'Solicitud + documentación + croquis'),
    ], string='Sección habilitada para actualizar desde el portal',
       required=True, default='none', copy=False, tracking=True, index=True)
    portal_update_allowed = fields.Boolean(
        string='Actualización desde portal habilitada', compute='_compute_portal_update_allowed',
        store=True, copy=False)
    portal_update_allowed_at = fields.Datetime(
        string='Permiso actualizado el', copy=False, readonly=True)
    portal_update_allowed_by = fields.Many2one(
        'res.users', string='Permiso actualizado por', readonly=True, copy=False)

    @api.depends('portal_update_scope')
    def _compute_portal_update_allowed(self):
        for record in self:
            record.portal_update_allowed = record.portal_update_scope not in (False, 'none')

    def portal_enabled_sections(self):
        """Secciones autorizadas para esta solicitud, sin afectar etapas."""
        self.ensure_one()
        return PORTAL_SCOPE_SECTIONS.get(self.portal_update_scope or 'none', frozenset())

    @api.model
    def portal_scope_from_sections(self, sections):
        enabled = frozenset(sections)
        for scope, members in PORTAL_SCOPE_SECTIONS.items():
            if members == enabled:
                return scope
        raise ValueError(_('Combinación no válida de permisos del portal.'))

    def portal_can_update_history(self):
        return 'history' in self.portal_enabled_sections()

    def portal_can_update_documentation(self):
        return 'documentation' in self.portal_enabled_sections()

    def portal_can_update_sketch(self):
        return 'sketch' in self.portal_enabled_sections()

    credit_access_button_visible = fields.Boolean(
        string='Puede conceder permisos del portal', compute='_compute_credit_access_button_visible'
    )

    @api.depends('portal_user_id')
    @api.depends_context('uid')
    def _compute_credit_access_button_visible(self):
        authorized = (
            (
                self.env.user.has_group('custom_web_credito_conedera.group_credit_portal_update_manager')
                and self.env.user.has_group('custom_web_credito_conedera.group_credit_manager')
            )
            or self.env.user.has_group('custom_web_credito_conedera.group_credit_administrator')
        )
        for record in self:
            record.credit_access_button_visible = bool(authorized and record.portal_user_id)

    @api.depends('documents_unlocked', 'stage_id.is_approved', 'stage_id.is_documents_received', 'history_ids.stage_id.is_approved')
    def _compute_document_access_allowed(self):
        for record in self:
            approval_recorded = bool(record.history_ids.filtered(lambda h: h.stage_id.is_approved))
            record.document_access_allowed = bool(
                record.documents_unlocked and record.stage_id and
                (record.stage_id.is_approved or
                 (record.stage_id.is_documents_received and approval_recorded))
            )

    @api.model
    def _blocking_application(self, user_id, exclude_id=False, company_id=None):
        domain = [('portal_user_id', '=', user_id),
                  ('stage_id.is_approved', '=', False), ('stage_id.is_rejected', '=', False),
                  ('documents_unlocked', '=', False)]
        if company_id:
            domain.append(('company_id', '=', company_id))
        if exclude_id:
            domain.append(('id', '!=', exclude_id))
        return self.with_context(active_test=False).sudo().search(domain, limit=1)

    _credit_verification_result_fields = (
        ('inspection_done', 'Se realizó la inspección'),
        ('address_found', 'Se encontró la dirección'),
        ('client_lives_there', 'El cliente vive en esa dirección'),
        ('sketch_needed', 'Necesita croquis'),
    )

    def _credit_complete_verification_values(self, vals):
        """Cierra la verificación automáticamente solo cuando hay cuatro respuestas y responsable.

        El personal no necesita modificar un estado técnico. Mientras falte un dato, la
        inspección puede guardarse en revisión, pero nunca aprobarse/rechazarse.
        """
        self.ensure_one()
        get_value = lambda key: vals.get(key, self[key])
        all_answers = all(get_value(key) in ('yes', 'no') for key, _ in self._credit_verification_result_fields)
        responsible = bool((get_value('verifier_name') or '').strip())
        if all_answers and responsible:
            outcome = ('verified' if get_value('inspection_done') == 'yes' and
                       get_value('address_found') == 'yes' else 'failed')
            if get_value('verification_status') != outcome:
                vals['verification_status'] = outcome
            if not get_value('verification_completed_at'):
                vals['verification_completed_at'] = fields.Datetime.now()
        else:
            if get_value('verification_status') in ('verified', 'failed'):
                vals['verification_status'] = 'in_progress'
                vals['verification_completed_at'] = False
        return vals

    @api.constrains(
        'verification_status', 'verification_completed_at', 'stage_id', 'inspection_done',
        'address_found', 'client_lives_there', 'sketch_needed', 'verifier_name',
    )
    def _check_credit_decision(self):
        for record in self:
            final_stage = bool(record.stage_id and (record.stage_id.is_approved or record.stage_id.is_rejected))
            final_verification = record.verification_status in ('verified', 'failed')
            if final_stage or final_verification:
                missing = [label for field, label in self._credit_verification_result_fields if record[field] not in ('yes', 'no')]
                if not (record.verifier_name or '').strip():
                    missing.append('Nombre del verificador')
                if not record.verification_completed_at:
                    missing.append('Fecha de verificación')
                if missing:
                    raise ValidationError(_('Complete los campos obligatorios de Resultados de la verificación y Responsable y cierre: %s.') % ', '.join(missing))
            if record.stage_id.is_approved and (record.verification_status != 'verified' or
                    record.inspection_done != 'yes' or record.address_found != 'yes' or
                    not record.verification_address):
                raise ValidationError(_('Antes de aprobar debe terminar la verificación correctamente: inspección realizada, dirección encontrada, ubicación registrada por el cliente y responsable identificado.'))
            if record.stage_id.is_rejected and record.verification_status not in ('verified', 'failed'):
                raise ValidationError(_('Antes de rechazar complete todos los resultados y el responsable de la verificación.'))

    @api.model
    def _get_company_credit_sequence(self, company_id):
        """Obtiene una secuencia exclusiva por empresa, sin reiniciar expedientes históricos.

        La numeración de las empresas que ya tenían solicitudes continúa desde
        el número máximo propio. Las empresas nuevas empiezan en 00001.
        """
        company = self.env['res.company'].sudo().browse(int(company_id)).exists()
        if not company:
            raise ValidationError(_('Seleccione una empresa válida para generar la solicitud.'))

        # Protege la creación inicial de la secuencia si llegan dos solicitudes
        # simultáneas desde el mismo dominio.
        self.env.cr.execute('SELECT pg_advisory_xact_lock(%s, %s)', (184141, company.id))
        Sequence = self.env['ir.sequence'].sudo().with_company(company)
        sequences = Sequence.search([
            ('code', '=', 'conedera.credit.application'),
            ('company_id', '=', company.id),
        ], order='id', limit=1)
        if sequences:
            return sequences

        # Los nombres existentes son definitivos. Nunca se renumeran ni se
        # mezclan contadores de compañías distintas durante la actualización.
        self.env.cr.execute("""
            SELECT COALESCE(MAX(substring(name from '^CRED/[0-9]{4}/([0-9]+)$')::integer), 0)
              FROM conedera_credit_application
             WHERE company_id = %s
               AND name ~ '^CRED/[0-9]{4}/[0-9]+$'
        """, (company.id,))
        maximum_existing = self.env.cr.fetchone()[0] or 0
        return Sequence.create({
            'name': _('Solicitudes de crédito - %s') % company.name,
            'code': 'conedera.credit.application',
            'company_id': company.id,
            'prefix': 'CRED/%(year)s/',
            'padding': 5,
            'number_increment': 1,
            'number_next': maximum_existing + 1,
            'implementation': 'standard',
        })

    @api.model
    def _ensure_company_credit_sequences(self):
        """Provisiona compañías actuales durante la actualización del módulo."""
        for company in self.env['res.company'].sudo().search([]):
            self._get_company_credit_sequence(company.id)
        return True

    @api.constrains('partner_id', 'company_id')
    def _check_credit_partner_company(self):
        for application in self:
            if (application.partner_id.company_id and
                    application.partner_id.company_id != application.company_id):
                raise ValidationError(_(
                    'El contacto solicitante debe ser compartido o pertenecer a la misma empresa que la solicitud.'))

    @api.onchange('applicant_name', 'partner_id')
    def _onchange_credit_partner_id(self):
        """Usar los datos del contacto como punto de partida de una solicitud manual.

        Es una copia inicial: los datos del expediente no modifican la ficha del
        contacto al editarla desde el backend.
        """
        for application in self:
            partner = application.applicant_name or application.partner_id
            if not partner:
                continue
            application.partner_id = partner
            is_company = bool(partner.is_company)
            kind = 'juridical' if is_company else 'natural'
            applicant_type = self.env['conedera.credit.applicant.type'].sudo().search(
                [('code', '=', kind), ('active', '=', True)], limit=1)
            if applicant_type:
                application.applicant_type_id = applicant_type
            vat = (partner.vat or '').strip()
            document_type = ('ruc' if is_company or len(vat) == 13 else
                             'cedula' if valid_credit_identity(vat, 'cedula') else 'foreign')
            if vat:
                application.identification = vat
                application.identification_type = document_type
            elif is_company:
                application.identification_type = 'ruc'
            application.applicant_name_text = partner.name or False
            application.applicant_email = partner.email or False
            application.mobile = partner.mobile or partner.phone or False
            application.phone_fixed = partner.phone or False
            application.home_address = partner.street or False
            application.business_name = partner.commercial_partner_id.name or partner.name or False
            application.business_ruc = vat if len(vat) == 13 else False
            application.business_address = partner.street or partner.contact_address or False
            application.business_phone = partner.phone or partner.mobile or False
            application.city = partner.city or False
            if partner.email:
                application.representative_email = partner.email

    @api.model
    def _credit_partner_record(self, vals, company_id=None, portal_user_id=None):
        """Buscar por documento y reutilizar contacto; crear solamente si no existe.

        Distingue el representante (res.users.partner_id) del negocio jurídico.
        Nunca sobreescribe automáticamente un cliente comercial existente.
        """
        company = self.env['res.company'].sudo().browse(
            company_id or vals.get('company_id') or self.env.company.id).exists()
        if not company:
            raise ValidationError(_('Seleccione una empresa válida para la solicitud.'))
        Partner = self.env['res.partner'].sudo().with_company(company)
        applicant_type = self.env['conedera.credit.applicant.type'].sudo().browse(
            vals.get('applicant_type_id')).exists()
        is_company = bool(applicant_type and applicant_type.code == 'juridical')
        identity = (vals.get('business_ruc') if is_company else vals.get('identification')) or ''
        identity = str(identity).strip()
        if not identity:
            raise ValidationError(_('Ingrese el documento de identificación antes de vincular un contacto.'))
        marker = 'CONEDERA-CRED:%s:%s' % ('J' if is_company else 'N', identity)
        # Impedir crear dos contactos simultáneos para el mismo documento.
        key = zlib.crc32(('%s:%s:%s' % (company.id, is_company, identity)).encode('utf-8'))
        if key >= 2**31:
            key -= 2**32
        self.env.cr.execute('SELECT pg_advisory_xact_lock(%s, %s)', (184148, key))
        domain_company = ['|', ('company_id', '=', False), ('company_id', '=', company.id)]
        matches = Partner.with_context(active_test=False).search(
            domain_company + ['|', ('vat', '=ilike', identity), ('ref', '=', marker)],
            order='id', limit=100)
        matches = matches.filtered(lambda p: bool(p.is_company) == is_company)
        user_partner = self.env['res.partner']
        if portal_user_id:
            user = self.env['res.users'].sudo().browse(portal_user_id).exists()
            user_partner = user.partner_id if user else user_partner
        if user_partner and user_partner in matches:
            return user_partner
        local_match = matches.filtered(lambda p: p.company_id == company)
        if local_match:
            return local_match[0]
        if matches:
            return matches[0]
        # El usuario ya tiene contacto creado al registrarse por OTP. Reutilizar
        # ese contacto cuando realmente es la misma persona natural.
        email = (vals.get('applicant_email') or '').strip().lower()
        if (not is_company and user_partner and not user_partner.is_company and
                user_partner.company_id.id in (False, company.id) and
                (not user_partner.vat or user_partner.vat.strip() == identity) and
                email and (user_partner.email or '').strip().lower() == email):
            if not user_partner.vat:
                # La validación fiscal de Contactos puede ser más estricta que
                # la de la solicitud. Conservar la identificación en ref cuando
                # Odoo rechace el documento como VAT de un contacto.
                try:
                    with self.env.cr.savepoint():
                        user_partner.sudo().write({'vat': identity})
                except ValidationError:
                    user_partner.sudo().write({'ref': marker})
            return user_partner
        # Reutilizar también un contacto que ya exista sin VAT si coinciden
        # exactamente nombre y email (sin escoger arbitrariamente entre duplicados).
        target_name = ((vals.get('business_name') if is_company else vals.get('applicant_name_text')) or '').strip()
        lookup_email = (vals.get('invoice_email') or vals.get('representative_email') or
                        vals.get('applicant_email')) if is_company else vals.get('applicant_email')
        if target_name and lookup_email:
            candidates = Partner.with_context(active_test=False).search(
                domain_company + [('vat', '=', False), ('email', '=ilike', str(lookup_email).strip())],
                order='id', limit=100).filtered(
                    lambda p: p.is_company == is_company and
                    (p.name or '').strip().casefold() == target_name.casefold())
            if len(candidates) == 1:
                return candidates
        data = {
            'name': (vals.get('business_name') if is_company else vals.get('applicant_name_text')) or _('Solicitante de crédito'),
            'is_company': is_company,
            'company_type': 'company' if is_company else 'person',
            'company_id': company.id,
            'vat': identity,
            'email': (vals.get('invoice_email') or vals.get('representative_email') or
                      vals.get('applicant_email')) if is_company else vals.get('applicant_email'),
            'phone': (vals.get('business_phone') if is_company else vals.get('phone_fixed')) or False,
            'mobile': (vals.get('mobile') if not is_company else False),
            'street': (vals.get('business_address') if is_company else vals.get('home_address')) or False,
            'city': vals.get('city') if is_company else False,
        }
        try:
            with self.env.cr.savepoint():
                return Partner.create(data)
        except ValidationError:
            # El requisito de Odoo/contabilidad sobre RUC puede ser distinto
            # del del portal. La solicitud conserva el documento exacto.
            data.pop('vat')
            data['ref'] = marker
            _logger.warning('El identificador %s no pasó la validación VAT de Contactos; se guardó en referencia.', identity)
            return Partner.create(data)

    @api.model
    def _migrate_credit_partner_links(self):
        """Vincular expedientes anteriores sin cambiar sus datos ni sus etapas."""
        # Solo los expedientes previos (sin partner_id) se consideran históricos.
        # Nunca reclasificar manualmente expedientes nuevos en actualizaciones posteriores.
        self.env.cr.execute("""
            UPDATE conedera_credit_application
               SET credit_origin = 'portal'
             WHERE portal_user_id IS NOT NULL AND partner_id IS NULL
        """)
        applications = self.sudo().with_context(active_test=False).search([('partner_id', '=', False)])
        updated = 0
        for application in applications:
            if not (application.applicant_type_id and application.company_id):
                continue
            try:
                with self.env.cr.savepoint():
                    values = {key: application[key] for key in (
                        'identification', 'business_ruc', 'applicant_name_text', 'business_name',
                        'applicant_email', 'invoice_email', 'representative_email', 'mobile',
                        'phone_fixed', 'business_phone', 'home_address', 'business_address', 'city')}
                    values['applicant_type_id'] = application.applicant_type_id.id
                    values['company_id'] = application.company_id.id
                    partner = self._credit_partner_record(
                        values, company_id=application.company_id.id,
                        portal_user_id=application.portal_user_id.id)
                    application.with_context(credit_migrating_partner=True).write({'partner_id': partner.id})
                    updated += 1
            except (ValidationError, AccessError, UserError, ValueError):
                _logger.exception('No se pudo vincular contacto para la solicitud %s', application.name)
        _logger.info('Solicitudes históricas vinculadas a Contactos: %s', updated)
        return True

    @api.model
    def _migrate_credit_applicant_name_partner(self):
        """Backfill técnico applicant_name (res.partner) sin perder los nombres.

        La migración SQL previa conservó el antiguo texto en applicant_name_text.
        El enlace existente partner_id es la fuente de verdad; para expedientes
        sin enlace, intentar la migración histórica por identificación/RUC.
        """
        self._migrate_credit_partner_links()
        # La relación almacenada se recalculará por la dependencia de partner_id;
        # invalidamos caché para que también se refleje en esta actualización.
        applications = self.sudo().with_context(active_test=False).search([])
        missing = applications.filtered(lambda a: not a.partner_id)
        _logger.info('Migración solicitante res.partner: total=%s enlazadas=%s sin_contacto=%s',
                     len(applications), len(applications) - len(missing), len(missing))
        for app in missing:
            _logger.warning('La solicitud %s no tiene contacto asociable; revisar documento %s',
                            app.name, app.identification)
        return True

    @api.model_create_multi
    def create(self, vals_list):
        Stage = self.env['conedera.credit.stage']
        required_consents = (
            'declaration_accepted', 'prior_commercial_relationship_accepted',
            'electronic_service_accepted', 'credit_bureau_authorized',
            'company_signature_stamp_acknowledged', 'additional_financial_documents_accepted',
        )
        # Bloqueo por usuario, comprobación por pareja (usuario, empresa).
        # Un cliente puede solicitar crédito en dos empresas distintas, pero
        # solo tener una solicitud pendiente en cada empresa.
        user_ids = sorted({v.get('portal_user_id') for v in vals_list if v.get('portal_user_id')})
        for user_id in user_ids:
            self.env.cr.execute('SELECT id FROM res_users WHERE id = %s FOR UPDATE', (user_id,))
        for user_id, company_id in sorted({
                (v.get('portal_user_id'), v.get('company_id') or self.env.company.id)
                for v in vals_list if v.get('portal_user_id')}):
            if self._blocking_application(user_id, company_id=company_id):
                raise ValidationError(_('Ya tiene una solicitud en trámite para esta empresa. Solo podrá registrar otra cuando la anterior esté aprobada o rechazada.'))
        seen_users = set()
        for vals in vals_list:
            # El backend usa applicant_name como selector Many2one. El campo
            # partner_id queda sincronizado para mantener todas las relaciones.
            if 'applicant_name' in vals:
                # Campo visible del backend: la selección se refleja en partner_id.
                vals['partner_id'] = vals.pop('applicant_name')
            user_id = vals.get('portal_user_id')
            user_company = (user_id, vals.get('company_id') or self.env.company.id)
            if user_id and user_company in seen_users:
                raise ValidationError(_('Solo puede crear una solicitud en trámite por usuario.'))
            if user_id:
                seen_users.add(user_company)
            from_portal = bool(self.env.context.get('credit_portal_submission'))
            if from_portal:
                if not user_id:
                    raise ValidationError(_('La solicitud web requiere una sesión de usuario.'))
                if not all(vals.get(field) for field in required_consents):
                    raise ValidationError(_('Para guardar una nueva solicitud debe aceptar la declaración general y todas las condiciones adicionales.'))
                vals['credit_origin'] = 'portal'
                # El contacto NO proviene de un valor enviado por el navegador.
                vals['partner_id'] = self._credit_partner_record(
                    vals, portal_user_id=user_id).id
            else:
                vals['credit_origin'] = 'backend'
                if not vals.get('partner_id'):
                    raise ValidationError(_('Seleccione el solicitante desde Contactos.'))
                # Nueva solicitud manual: por defecto usar el nombre del contacto.
                if not vals.get('applicant_name_text'):
                    partner = self.env['res.partner'].browse(vals['partner_id'])
                    vals['applicant_name_text'] = partner.name or False
            if not vals.get('applicant_type_id'):
                raise ValidationError(_('Seleccione un tipo de solicitante configurado.'))
            if vals.get('name', 'Nuevo') == 'Nuevo':
                company_id = vals.get('company_id') or self.env.company.id
                sequence = self._get_company_credit_sequence(company_id)
                vals['name'] = sequence.next_by_id() or _('Nuevo')
            if not vals.get('stage_id'):
                initial = Stage.search([('is_initial', '=', True), ('active', '=', True)], order='sequence,id', limit=1)
                if not initial:
                    initial = Stage.search([('active', '=', True)], order='sequence,id', limit=1)
                if initial:
                    vals['stage_id'] = initial.id
            stage = Stage.browse(vals.get('stage_id')) if vals.get('stage_id') else Stage
            if stage and stage.is_documents_received:
                raise ValidationError(_('La recepción de documentos solo puede ocurrir después de aprobar una solicitud existente.'))
            # El campo no puede habilitarse manualmente desde create/ORM.
            vals['documents_unlocked'] = bool(stage and stage.is_approved)
            if vals.get('declaration_accepted'):
                vals['declaration_date'] = fields.Datetime.now()
        records = super().create(vals_list)
        for record in records:
            if record.stage_id:
                self.env['conedera.credit.stage.history'].sudo().create({
                    'application_id': record.id,
                    'stage_id': record.stage_id.id,
                    'user_id': self.env.user.id,
                    'notes': _('Solicitud registrada desde el portal') if record.credit_origin == 'portal' else _('Solicitud registrada manualmente desde Odoo'),
                    'visible_to_portal': True,
                })
            record.message_post(body=_('Solicitud registrada. Etapa inicial: %s') % escape(record.stage_id.name or ''))
            if record.stage_id.is_initial:
                record._send_stage_notification(False, record.stage_id)
        return records

    def write(self, vals):
        self._check_reviewer_values(vals)
        protected_consents = (
            'declaration_accepted', 'prior_commercial_relationship_accepted',
            'electronic_service_accepted', 'credit_bureau_authorized',
            'company_signature_stamp_acknowledged', 'additional_financial_documents_accepted',
        )
        if any(field in vals and not vals[field] for field in protected_consents):
            raise ValidationError(_('No es posible quitar una aceptación registrada en una solicitud de crédito.'))
        verification_fields = {key for key, _label in self._credit_verification_result_fields} | {
            'verifier_name', 'verification_status', 'stage_id'
        }
        if verification_fields.intersection(vals):
            # En operaciones masivas, cada expediente puede tener respuestas diferentes.
            # Evaluarlas por separado evita asignar por error el mismo resultado a todos.
            if len(self) > 1:
                for record in self:
                    record.write(dict(vals))
                return True
            if self:
                vals = self._credit_complete_verification_values(dict(vals))
        if 'applicant_type_id' in vals and not vals['applicant_type_id']:
            raise ValidationError(_('El tipo de solicitante es obligatorio.'))
        if 'applicant_type_id' in vals:
            for record in self:
                if record.document_ids and record.applicant_type_id and record.applicant_type_id.id != vals['applicant_type_id']:
                    raise ValidationError(_('No cambie el tipo de solicitante de una solicitud que ya contiene documentación.'))
        previous_stages = {record.id: record.stage_id for record in self} if 'stage_id' in vals else {}
        values = dict(vals)
        if 'applicant_name' in values:
            if self.env.context.get('credit_portal_submission'):
                raise AccessError(_('El solicitante se identifica automáticamente desde el servidor.'))
            # applicant_name es el selector de contacto; preferirlo a cualquier
            # valor desactualizado del campo técnico partner_id.
            values['partner_id'] = values.pop('applicant_name')
        if ('partner_id' in values and values['partner_id'] and
                not self.env.context.get('credit_portal_submission') and
                not self.env.context.get('credit_migrating_partner') and
                'applicant_name_text' not in values):
            values['applicant_name_text'] = self.env['res.partner'].browse(values['partner_id']).name or False
        if (self.env.context.get('credit_portal_submission') and
                {'identification', 'business_ruc', 'applicant_type_id'}.intersection(values)):
            if len(self) > 1:
                for record in self:
                    record.write(dict(values))
                return True
            if self:
                values_for_match = {key: values.get(key, self[key]) for key in (
                    'identification', 'business_ruc', 'applicant_name_text', 'business_name',
                    'applicant_email', 'invoice_email', 'representative_email', 'mobile',
                    'phone_fixed', 'business_phone', 'home_address', 'business_address', 'city')}
                values_for_match['company_id'] = self.company_id.id
                values_for_match['applicant_type_id'] = values.get('applicant_type_id', self.applicant_type_id.id)
                values['partner_id'] = self._credit_partner_record(
                    values_for_match, company_id=self.company_id.id,
                    portal_user_id=self.portal_user_id.id).id
        if 'stage_id' in values:
            new_stage = self.env['conedera.credit.stage'].browse(values.get('stage_id'))
            if new_stage.is_documents_received:
                for record in self:
                    approved_before = bool(record.stage_id.is_approved or (
                        record.documents_unlocked and record.stage_id.is_documents_received and
                        any(h.stage_id.is_approved for h in record.history_ids)
                    ))
                    if not approved_before:
                        raise ValidationError(_('No puede ingresar documentación sin la aprobación previa de la solicitud.'))
                values['documents_unlocked'] = True
            else:
                # Impedir que un estado 'En revisión' conserve el indicador de
                # documentos habilitados cuando se revierte una aprobación.
                values['documents_unlocked'] = bool(new_stage.is_approved)
        elif 'documents_unlocked' in values:
            # Nadie debe habilitar documentos manualmente antes de la aprobación.
            for record in self:
                if values['documents_unlocked'] and not (
                    record.stage_id.is_approved or record.stage_id.is_documents_received
                ):
                    raise ValidationError(_('Solo la etapa Aprobada puede habilitar el ingreso de documentos.'))
        if values.get('declaration_accepted'):
            values.setdefault('declaration_date', fields.Datetime.now())
        result = super().write(values)
        if {'signed_application_attachment_ids', 'signed_verification_attachment_ids'}.intersection(values):
            for application in self:
                for att in (application.signed_application_attachment_ids |
                            application.signed_verification_attachment_ids):
                    if att.res_model != self._name or att.res_id != application.id or att.public:
                        att.sudo().write({'res_model': self._name,
                                          'res_id': application.id, 'public': False})
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
                if record.stage_id.is_initial or record.stage_id.is_approved:
                    record._send_stage_notification(old_stage, record.stage_id)
        return result

    def _send_stage_notification(self, old_stage, new_stage):
        self.ensure_one()
        if not (new_stage.is_initial or new_stage.is_approved):
            return
        email = self.applicant_email or self.portal_user_id.email or self.portal_user_id.login
        if not email:
            return
        try:
            body = _(
                '<p>Estimado/a %(name)s:</p>'
                '<p>La solicitud de crédito <b>%(number)s</b> registra un cambio de etapa.</p>'
                '<p>Estado anterior: %(old)s<br/>Estado actual: <b>%(new)s</b></p>'
                '<p>%(access_note)s</p>'
            ) % {
                'name': escape(self.applicant_name_text or self.applicant_name.name or self.portal_user_id.name or ''),
                'number': escape(self.name or ''),
                'old': escape(old_stage.name if old_stage else '-'),
                'new': escape(new_stage.name or '-'),
                'company': escape(self.company_id.name or ''),
                'access_note': (_('Puede consultar el historial ingresando al portal de CONEDERA.')
                                if self.portal_user_id else
                                _('Este expediente fue registrado por el equipo de CONEDERA.')),
            }
            # Usar el SMTP independiente del módulo de crédito y su smtp_user
            # como remitente. No reutilizar ni alterar la configuración de RR. HH.
            credit_mail_server = self.env['ir.mail_server'].sudo().get_conedera_credit_mail_server()
            mail = self.env['mail.mail'].sudo().create({
                'subject': _('Actualización de solicitud de crédito %s') % self.name,
                'body_html': body,
                'email_to': email,
                'email_from': (credit_mail_server.smtp_user or '').strip(),
                'mail_server_id': credit_mail_server.id,
            })
            mail.send()
        except Exception:
            _logger.exception('No se pudo notificar por correo la etapa de solicitud %s', self.name)

    def action_open_portal_update_wizard(self):
        """Botón inteligente y de cabecera, igual al permiso de postulaciones."""
        self.ensure_one()
        if not (
            (
                self.env.user.has_group('custom_web_credito_conedera.group_credit_portal_update_manager')
                and self.env.user.has_group('custom_web_credito_conedera.group_credit_manager')
            )
            or self.env.user.has_group('custom_web_credito_conedera.group_credit_administrator')
        ):
            raise AccessError(_('No puede gestionar permisos de actualización del portal de crédito.'))
        if not self.portal_user_id:
            raise UserError(_('Esta solicitud no tiene un usuario de portal asociado.'))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Habilitar permiso del portal'),
            'res_model': 'conedera.credit.access.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_application_id': self.id,
            },
        }

    # Mantiene compatible la acción del botón de versiones anteriores.
    def action_open_access_wizard(self):
        return self.action_open_portal_update_wizard()

    def action_open_portal(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_url',
            'url': '/my/credito/%s' % self.id,
            'target': 'new',
        }

    @api.constrains('phone_fixed', 'business_phone', 'employment_phone')
    def _check_numeric_phones(self):
        for record in self:
            for field_name, label in (
                ('phone_fixed', _('Teléfono fijo')),
                ('business_phone', _('Teléfono de la empresa')),
                ('employment_phone', _('Teléfono del empleador')),
            ):
                phone = record[field_name] or ''
                if phone and not re.fullmatch(r'[0-9]+', phone):
                    raise ValidationError(_('%s debe contener únicamente dígitos numéricos.') % label)

    @api.constrains('identification', 'identification_type', 'spouse_identification', 'authorized_buyer_identification', 'authorized_pickup_identification', 'mobile', 'business_ruc', 'marital_status_id', 'spouse_name', 'spouse_profession', 'business_latitude', 'business_longitude')
    def _check_ecuador_contact_fields(self):
        # No bloquear actualizaciones de catálogos para expedientes históricos
        # incompletos que ya existían antes de introducir estos requisitos.
        if self.env.context.get('credit_catalog_migration'):
            return
        for record in self:
            if record.identification and not valid_credit_identity(record.identification.strip(), record.identification_type):
                raise ValidationError(_('El documento del solicitante no cumple la validación del tipo seleccionado.'))
            if record.business_ruc and not valid_ruc_length(record.business_ruc.strip()):
                raise ValidationError(_('El RUC del negocio debe tener exactamente 13 dígitos numéricos.'))
            if record.mobile and not valid_ecuador_mobile(record.mobile.strip()):
                raise ValidationError(_('El celular debe tener exactamente 10 dígitos numéricos.'))
            if record.spouse_identification and not valid_ecuador_or_foreign_document(record.spouse_identification.strip()):
                raise ValidationError(_('El documento del cónyuge debe contener exactamente 10 dígitos; se admite cédula ecuatoriana o documento extranjero numérico.'))
            for field_name, label in (
                ('authorized_buyer_identification', _('persona autorizada a comprar')),
                ('authorized_pickup_identification', _('persona autorizada a retirar mercadería')),
            ):
                document = (record[field_name] or '').strip()
                if document and not valid_ecuador_or_foreign_document(document):
                    raise ValidationError(_(
                        'El documento de %(person)s debe tener 10 dígitos numéricos; '
                        'se valida primero como cédula ecuatoriana y, si no corresponde, como documento extranjero.'
                    ) % {'person': label})
            needs_spouse = record.marital_status_id.requires_spouse
            if needs_spouse and not all((record.spouse_name, record.spouse_identification, record.spouse_profession)):
                raise ValidationError(_('Para casado/a o unión de hecho complete nombres, documento y profesión del cónyuge.'))
            if (record.business_latitude or record.business_longitude) and not (-90 <= record.business_latitude <= 90 and -180 <= record.business_longitude <= 180):
                raise ValidationError(_('La latitud debe estar entre -90 y 90, y la longitud entre -180 y 180.'))

    @api.constrains('dependents_count', 'monthly_sales', 'social_capital', 'assets_amount', 'monthly_income', 'liabilities_amount', 'monthly_expenses', 'vehicle1_value', 'vehicle2_value', 'employment_salary')
    def _check_non_negative_amounts(self):
        for record in self:
            if record.dependents_count < 0:
                raise ValidationError(_('El número de cargas no puede ser negativo.'))
            for field_name in ('monthly_sales', 'social_capital', 'assets_amount', 'monthly_income', 'liabilities_amount', 'monthly_expenses', 'vehicle1_value', 'vehicle2_value', 'employment_salary'):
                if record[field_name] < 0:
                    raise ValidationError(_('Los montos de la solicitud no pueden ser negativos.'))

    @api.model
    def _migrate_credit_company(self):
        """Assign a legacy company only where old versions had no company field.

        Historical forms never saved their website company: use the upgrade
        environment's company as a fallback, and expose it for audit/editing.
        """
        legacy = self.sudo().with_context(active_test=False).search([('company_id', '=', False)])
        if legacy:
            legacy.write({'company_id': self.env.company.id})
            _logger.warning('Asignada empresa %s a %s solicitudes anteriores sin empresa; revisar asignación multiempresa.', self.env.company.display_name, len(legacy))

    @api.model
    def _migrate_credit_configuration(self):
        """Migración repetible al actualizar: enlaza solicitudes y conserva archivos antiguos."""
        Type = self.env['conedera.credit.applicant.type'].sudo()
        mapping = {
            'natural': Type.search([('code', '=', 'natural')], limit=1),
            'juridical': Type.search([('code', '=', 'juridical')], limit=1),
        }
        for old_code, applicant_type in mapping.items():
            if not applicant_type:
                continue
            applications = self.sudo().search([
                ('applicant_type_id', '=', False), ('person_type', '=', old_code),
            ])
            if applications:
                applications.write({'applicant_type_id': applicant_type.id})

        # Migración de identificaciones históricas: antes se aceptaba cédula o RUC.
        self.env.cr.execute("""UPDATE conedera_credit_application
            SET identification_type = CASE WHEN length(identification) = 13 THEN 'ruc' ELSE 'cedula' END
            WHERE identification_type IS NULL
               OR (identification_type = 'cedula' AND length(identification) = 13)""")
        # La etapa de verificación antigua deja de ser una fase obligatoria
        # del kanban: ahora tiene estado independiente en cada solicitud.
        old_verification_stage = self.env.ref('custom_web_credito_conedera.stage_credit_verification', raise_if_not_found=False)
        review_stage = self.env.ref('custom_web_credito_conedera.stage_credit_review', raise_if_not_found=False)
        if old_verification_stage and review_stage:
            # La antigua etapa era secuencial. Volver a revisión preservando
            # una marca independiente para los expedientes que ya la utilizaban.
            self.env.cr.execute("""UPDATE conedera_credit_application
                SET stage_id = %s, verification_status = 'in_progress'
                WHERE stage_id = %s RETURNING id""", (review_stage.id, old_verification_stage.id))
            migrated_ids = [row[0] for row in self.env.cr.fetchall()]
            if migrated_ids:
                self.invalidate_model(['stage_id', 'verification_status'])
                for application_id in migrated_ids:
                    self.env['conedera.credit.stage.history'].sudo().create({
                        'application_id': application_id, 'stage_id': review_stage.id,
                        'user_id': self.env.user.id,
                        'notes': _('Migración: revisión y verificación del negocio funcionan en paralelo.'),
                        'visible_to_portal': True,
                    })
        if old_verification_stage and old_verification_stage.active:
            old_verification_stage.active = False
        
        # Una sola inicialización para instalaciones que ya tenían el catálogo.
        # Luego el administrador puede personalizar requiere_cónyuge sin que
        # actualizaciones futuras sobrescriban su elección.
        Params = self.env['ir.config_parameter'].sudo()
        if not Params.get_param('conedera.credit.spouse_rules_initialized'):
            for code in ('married', 'free_union'):
                rule = self.env['conedera.credit.marital.status'].sudo().search([('code', '=', code)], limit=1)
                if rule and not rule.requires_spouse:
                    rule.requires_spouse = True
            Params.set_param('conedera.credit.spouse_rules_initialized', '1')

        # Los antiguos valores Selection permanecen disponibles; una sola
        # migración idempotente los relaciona con el nuevo catálogo de estados civiles.
        MaritalStatus = self.env['conedera.credit.marital.status'].sudo()
        for code in ('single', 'married', 'divorced', 'widowed', 'free_union', 'other'):
            status = MaritalStatus.search([('code', '=', code)], limit=1)
            if status:
                legacy_records = self.sudo().search([
                    ('marital_status_id', '=', False), ('marital_status', '=', code),
                ])
                if legacy_records:
                    legacy_records.with_context(credit_catalog_migration=True).write({'marital_status_id': status.id})
        # Catálogo nuevo de vivienda; se preservan los valores históricos.
        Housing = self.env['conedera.credit.housing.type'].sudo()
        for old_code in ('own', 'rented', 'family', 'mortgaged'):
            housing = Housing.search([('code', '=', old_code)], limit=1)
            if housing:
                old_requests = self.sudo().search([
                    ('housing_type_id', '=', False), ('housing_type', '=', old_code),
                ])
                if old_requests:
                    old_requests.write({'housing_type_id': housing.id})
        # Migrar ambos vehículos antiguos una sola vez, sin duplicarlos en actualizaciones.
        Vehicle = self.env['conedera.credit.vehicle'].sudo()
        legacy_fields = [
            'vehicle1_brand', 'vehicle1_model', 'vehicle1_year', 'vehicle1_value',
            'vehicle2_brand', 'vehicle2_model', 'vehicle2_year', 'vehicle2_value',
        ]
        conditions = [(field, '!=', 0 if field.endswith('_value') else False)
                      for field in legacy_fields]
        applications_with_legacy = self.sudo().search(
            [('legacy_vehicle_migrated', '=', False)] + ['|'] * (len(conditions) - 1) + conditions)
        for application in applications_with_legacy:
            for slot in (1, 2):
                item = {
                    'brand': application['vehicle%s_brand' % slot],
                    'model': application['vehicle%s_model' % slot],
                    'year': application['vehicle%s_year' % slot],
                    'value': application['vehicle%s_value' % slot],
                }
                if not any(item.values()):
                    continue
                if Vehicle.search_count([('application_id', '=', application.id), ('legacy_slot', '=', slot)]):
                    continue
                Vehicle.create(dict(item, application_id=application.id,
                                    sequence=slot * 10, legacy_slot=slot))
            application.write({'legacy_vehicle_migrated': True})
        # Los tipos creados anteriormente sin código adquieren un ID estable.
        for record in Type.search([('code', '=', False)]):
            new_code = self.env['ir.sequence'].next_by_code('conedera.credit.applicant.type')
            if not new_code:
                raise ValidationError(_('No se pudo generar el ID de un tipo de solicitante antiguo.'))
            record.with_context(credit_identifier_migration=True).write({'code': new_code})
        # La etapa para registrar documentación se identifica por un indicador,
        # nunca por su nombre: los administradores pueden renombrarla.
        docs_stage = self.env.ref('custom_web_credito_conedera.stage_credit_documents_received', raise_if_not_found=False)
        if docs_stage and not docs_stage.is_documents_received:
            docs_stage.is_documents_received = True
        # Una versión anterior conservaba documents_unlocked al volver a En revisión.
        # Corregirlo de manera idempotente sin borrar documentos ni el historial.
        self.env.cr.execute("""UPDATE conedera_credit_application AS app
            SET documents_unlocked = FALSE
            FROM conedera_credit_stage AS stage
            WHERE app.stage_id = stage.id AND app.documents_unlocked = TRUE
                AND NOT (stage.is_approved OR stage.is_documents_received)
        """)
        self.invalidate_model(['documents_unlocked'])

        # El almacenamiento binario original permanece intacto; las líneas nuevas
        # reciben una copia cuando el requisito inicial coincide con el campo viejo.
        Docs = self.env['conedera.credit.documents'].sudo()
        Line = self.env['conedera.credit.document.line'].sudo()
        Requirement = self.env['conedera.credit.document.requirement'].sudo()
        legacy_reqs = Requirement.search([('legacy_field', '!=', False)])
        for requirement in legacy_reqs:
            old_field = requirement.legacy_field
            if old_field not in Docs._fields:
                continue
            for doc in Docs.search([('application_id.applicant_type_id', '=', requirement.applicant_type_id.id)]):
                if Line.search_count([('document_id', '=', doc.id), ('requirement_id', '=', requirement.id)]):
                    continue
                # En Odoo, los binarios con attachment=True no siempre son
                # buscables por dominio: inspeccionamos el valor directamente.
                content = doc[old_field]
                if not content:
                    continue
                filename = doc[old_field + '_filename']
                if not filename:
                    # Se omite el archivo sin extensión verificable, pero se conserva
                    # siempre en su campo histórico para no perder información.
                    continue
                try:
                    with self.env.cr.savepoint():
                        Line.create({
                            'document_id': doc.id, 'requirement_id': requirement.id,
                            'file': content, 'filename': filename,
                        })
                except Exception:
                    _logger.exception('No se pudo trasladar archivo histórico %s del expediente %s; original conservado.', old_field, doc.id)
        # Catálogos editables: enlazar valores históricos una sola vez, sin
        # reescribir opciones escogidas manualmente por los administradores.
        for legacy_field, new_field, model_name, old_codes in (
            ('verification_zone', 'verification_zone_id', 'conedera.credit.verification.zone', ('urban', 'peripheral', 'rural')),
            ('verification_local_state', 'verification_local_state_id', 'conedera.credit.local.condition', ('very_good', 'good', 'regular', 'bad')),
        ):
            Catalog = self.env[model_name].sudo().with_context(active_test=False)
            for code in old_codes:
                catalog_record = Catalog.search([('code', '=', code)], limit=1)
                if catalog_record:
                    self.env.cr.execute(
                        'UPDATE conedera_credit_application SET %s = %%s WHERE %s IS NULL AND %s = %%s' %
                        (new_field, new_field, legacy_field),
                        (catalog_record.id, code),
                    )
        self.invalidate_model(['verification_zone_id', 'verification_local_state_id'])
        return True

    @api.model
    def _migrate_credit_employer_types(self):
        """Conservar las selecciones de empleador de expedientes antiguos."""
        catalog = self.env['conedera.credit.employer.type'].sudo().with_context(active_test=False)
        for code in ('private', 'public'):
            employer = catalog.search([('code', '=', code)], limit=1)
            if employer:
                self.env.cr.execute('''
                    UPDATE conedera_credit_application
                       SET employment_employer_type_id = %s
                     WHERE employment_employer_type_id IS NULL
                       AND employment_employer_type = %s
                ''', (employer.id, code))
        self.invalidate_model(['employment_employer_type_id'])
