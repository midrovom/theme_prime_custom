from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ConederaCreditApplicantType(models.Model):
    _name = 'conedera.credit.applicant.type'
    _description = 'Tipo de solicitante de crédito'
    _order = 'sequence, name, id'

    name = fields.Char(string='Tipo de solicitante', required=True, translate=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    code = fields.Char(
        string='ID único del tipo', copy=False, readonly=True, index=True,
        help='Identificador permanente (por ejemplo, natural, juridical, TC-000001). '
             'Puede utilizarse en integraciones y para localizar sus requisitos documentales.')
    note = fields.Text(string='Indicaciones para el solicitante')
    requirement_ids = fields.One2many('conedera.credit.document.requirement', 'applicant_type_id', string='Documentos exigidos')
    application_count = fields.Integer(compute='_compute_application_count', string='Solicitudes')

    _sql_constraints = [
        ('conedera_type_code_unique', 'unique(code)', 'Este código de tipo de solicitante ya está utilizado.'),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('code'):
                vals['code'] = self.env['ir.sequence'].next_by_code('conedera.credit.applicant.type')
                if not vals['code']:
                    raise ValidationError(_('No se pudo generar el identificador del tipo de solicitante.'))
        return super().create(vals_list)

    def write(self, vals):
        if 'code' in vals and not self.env.context.get('credit_identifier_migration'):
            raise ValidationError(_('El ID único del tipo de solicitante es permanente y no puede modificarse.'))
        return super().write(vals)

    @api.model
    def _ensure_standard_document_requirements(self):
        """One-off upgrade to the exact 7/8 documents requested for the two built-in types.

        Keep historical requirement rows and their uploaded files, but archive
        previously split prompts so they do not appear again in the portal.
        Other applicant types are not touched.
        """
        parameters = self.env['ir.config_parameter'].sudo()
        key = 'custom_web_credito_conedera.documents_exact_v1831'
        if parameters.get_param(key):
            return True
        mappings = {'natural': [('credit_requirement_natural_application_signed', 'Solicitud de crédito preparada y firmada por el solicitante', 10, False), ('credit_requirement_natural_ruc_updated', 'Copia del ruc actualizado.', 20, False), ('credit_requirement_natural_id_client', 'Copia a color de la cédula de ciudadanía del cliente y cónyuge.', 30, False), ('credit_requirement_natural_voting_certificate', 'Copia a color del certificado de votación vigente', 40, False), ('credit_requirement_natural_utility_business', 'Planilla de un servicio básico (luz, agua, teléfono, internet) del local y del lugar de residencia.', 50, False), ('credit_requirement_natural_local_photo_inside', 'Foto del local (parte interna y externa)', 60, False), ('credit_requirement_natural_applicant_signing_photo', 'Foto del solicitante firmando la solicitud de crédito, que se refleje el rostro con claridad.', 70, True)], 'juridical': [('credit_requirement_juridical_application_signed', 'Solicitud de crédito preparada y firmada por el representante legal', 10, False), ('credit_requirement_juridical_ruc_updated', 'Copia del ruc actualizado.', 20, False), ('credit_requirement_juridical_id_legal_representative', 'Copia a color de la cédula de ciudadanía del representante legal.', 30, False), ('credit_requirement_juridical_voting_legal_representative', 'Copia a color del certificado de votación vigente del representante legal.', 40, False), ('credit_requirement_juridical_utility_business', 'Planilla de un servicio básico (luz, agua, teléfono, internet) del local y del lugar de residencia.', 50, False), ('credit_requirement_juridical_legal_appointment', 'Nombramiento del representante legal', 60, False), ('credit_requirement_juridical_local_photo_inside', 'Foto del local (parte interna y externa)', 70, False), ('credit_requirement_juridical_applicant_signing_photo', 'Foto del solicitante firmando la solicitud de crédito, que se refleje el rostro con claridad.', 80, True)]}
        Requirement = self.env['conedera.credit.document.requirement'].sudo().with_context(active_test=False)
        for code, specifications in mappings.items():
            applicant_type = self.sudo().with_context(active_test=False).search([('code', '=', code)], limit=1)
            if not applicant_type:
                continue
            preserved = Requirement.browse()
            for xmlid, name, sequence, image_only in specifications:
                requirement = self.env.ref('custom_web_credito_conedera.' + xmlid, raise_if_not_found=False)
                if not requirement or requirement.applicant_type_id.id != applicant_type.id:
                    continue
                preserved |= requirement
                requirement.sudo().write({
                    'name': name, 'sequence': sequence, 'active': True,
                    'required': True, 'only_if_spouse': False,
                    'image_only': image_only, 'description': False,
                })
            extras = Requirement.search([('applicant_type_id', '=', applicant_type.id)]) - preserved
            if extras:
                # Never delete legacy requirements: previous uploads still reference them.
                extras.write({'active': False, 'required': False})
        parameters.set_param(key, '1')
        return True

    def _compute_application_count(self):
        for rec in self:
            rec.application_count = self.env['conedera.credit.application'].search_count([('applicant_type_id', '=', rec.id)])


class ConederaCreditDocumentRequirement(models.Model):
    _name = 'conedera.credit.document.requirement'
    _description = 'Documento configurable por tipo de solicitante'
    _order = 'sequence, id'

    name = fields.Char(string='Documento solicitado', required=True, translate=True)
    applicant_type_id = fields.Many2one('conedera.credit.applicant.type', required=True, ondelete='cascade', index=True, string='Tipo de solicitante')
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    required = fields.Boolean(string='Obligatorio', default=True)
    only_if_spouse = fields.Boolean(string='Solo cuando se declara cónyuge', help='Mostrar y exigir el documento únicamente si la solicitud indica cónyuge.')
    image_only = fields.Boolean(string='Solo fotografía (JPG/PNG)', default=False)
    pdf_only = fields.Boolean(string='Solo PDF', default=False)
    allow_multiple_files = fields.Boolean(string='Permitir varios archivos', default=False)
    minimum_files = fields.Integer(string='Archivos mínimos', default=1, required=True)
    description = fields.Text(string='Instrucciones para cargar el archivo')
    legacy_field = fields.Char(string='Campo anterior (migración)', readonly=True, copy=False,
        help='Se utiliza para conservar archivos cargados en versiones anteriores.')


    @api.constrains('minimum_files', 'allow_multiple_files', 'pdf_only', 'image_only')
    def _check_file_policy(self):
        for requirement in self:
            if requirement.minimum_files < 1 or requirement.minimum_files > 30:
                raise ValidationError(_('El mínimo de archivos debe estar entre 1 y 30.'))
            if not requirement.allow_multiple_files and requirement.minimum_files > 1:
                raise ValidationError(_('Para exigir más de un archivo debe activar «Permitir varios archivos».'))
            if requirement.pdf_only and requirement.image_only:
                raise ValidationError(_('Un requisito no puede ser «Solo PDF» y «Solo fotografía» al mismo tiempo.'))

    @api.model
    def _ensure_multiple_document_requirements(self):
        """Configura una sola vez los requisitos consolidados de ambos tipos estándar."""
        params = self.env['ir.config_parameter'].sudo()
        key = 'custom_web_credito_conedera.multiple_document_requirements_v1833'
        if params.get_param(key) == '1':
            return True
        for xmlid in ('credit_requirement_natural_utility_business',
                      'credit_requirement_juridical_utility_business'):
            req = self.env.ref('custom_web_credito_conedera.' + xmlid, raise_if_not_found=False)
            if req:
                req.sudo().write({'allow_multiple_files': True, 'minimum_files': 2,
                                  'pdf_only': True, 'image_only': False, 'required': True})
        for xmlid in ('credit_requirement_natural_local_photo_inside',
                      'credit_requirement_juridical_local_photo_inside'):
            req = self.env.ref('custom_web_credito_conedera.' + xmlid, raise_if_not_found=False)
            if req:
                req.sudo().write({'allow_multiple_files': True, 'minimum_files': 2,
                                  'pdf_only': False, 'image_only': True, 'required': True})
        params.set_param(key, '1')
        return True
