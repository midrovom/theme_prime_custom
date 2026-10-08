import base64

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


OPTIONAL_DOCUMENT_FIELDS = {
    'historia_iess',
    'acta_matrimonio',
    'documentos_hijos',
    'estudios_titulo',
    'cursos_realizados',
    'certificados_trabajo',
    'formulario_107',
}

DOCUMENT_FIELDS = [
    ('fotografia', 'Fotografía actualizada a color tamaño carnet', 'image'),
    ('cedula_votacion', '2 copias a color de cédula de identidad y certificado de votación', 'pdf'),
    ('hoja_vida_actualizada', 'Hoja de vida actualizada', 'pdf'),
    ('historia_iess', 'Historia laboral extraída de la página web del IESS (resumen de empleadores)', 'pdf'),
    ('acta_matrimonio', 'Acta de matrimonio ORIGINAL / unión de hecho registrada en cédula', 'pdf'),
    ('documentos_hijos', 'Hijos menores de 18 años: partida de nacimiento y/o cédula a color', 'pdf'),
    ('estudios_titulo', 'Certificado del último año de estudios o título certificado por SENESCYT', 'pdf'),
    ('cursos_realizados', 'Copias legibles de todos los cursos realizados, si tuviere', 'pdf'),
    ('recomendaciones', 'Mínimo 2 recomendaciones originales y actualizadas, no familiares', 'pdf'),
    ('certificados_trabajo', 'Certificados de trabajos anteriores', 'pdf'),
    ('planilla_servicios', 'Planilla de servicios básicos del lugar de residencia actualizada', 'pdf'),
    ('croquis_domicilio', 'Croquis del domicilio', 'pdf'),
    ('formulario_107', 'Formulario No. 107 del SRI', 'pdf'),
    ('cuenta_banco_internacional', 'Copia de cuenta de ahorros del Banco Internacional con nombre y número de cuenta', 'pdf'),
    ('certificado_salud', 'Certificado de salud del MSP con detalle de tipo de sangre', 'pdf'),
]


class ApplicantDocumentation(models.Model):
    _name = 'applicant.documentation'
    _description = 'Documentación de ingreso del postulante'
    _order = 'create_date desc, id desc'

    applicant_id = fields.Many2one(
        'hr.applicant',
        string='Postulación',
        required=True,
        ondelete='cascade',
        index=True,
    )

    fotografia = fields.Binary(string='Fotografía', attachment=True, required=True)
    fotografia_filename = fields.Char(string='Archivo fotografía', required=True)

    cedula_votacion = fields.Binary(string='Cédula / votación 1', attachment=True)
    cedula_votacion_filename = fields.Char(string='Archivo cédula / votación 1')
    cedula_votacion_2 = fields.Binary(string='Cédula / votación 2', attachment=True)
    cedula_votacion_filename_2 = fields.Char(string='Archivo cédula / votación 2')

    hoja_vida_actualizada = fields.Binary(string='Hoja de vida actualizada', attachment=True)
    hoja_vida_actualizada_filename = fields.Char(string='Archivo hoja de vida actualizada')

    historia_iess = fields.Binary(string='Historia laboral IESS', attachment=True)
    historia_iess_filename = fields.Char(string='Archivo historia IESS')

    acta_matrimonio = fields.Binary(string='Acta de matrimonio / unión de hecho', attachment=True)
    acta_matrimonio_filename = fields.Char(string='Archivo acta')

    documentos_hijos = fields.Binary(string='Documentos de hijos menores', attachment=True)
    documentos_hijos_filename = fields.Char(string='Archivo documentos hijos')

    estudios_titulo = fields.Binary(string='Estudios / título SENESCYT', attachment=True)
    estudios_titulo_filename = fields.Char(string='Archivo estudios / título')

    cursos_realizados = fields.Binary(string='Cursos realizados', attachment=True)
    cursos_realizados_filename = fields.Char(string='Archivo cursos')

    # Campo legado: se conserva para no perder información ya almacenada antes
    # de la migración al modelo de múltiples recomendaciones.
    recomendaciones = fields.Binary(string='Recomendación (legado)', attachment=True)
    recomendaciones_filename = fields.Char(string='Archivo recomendación (legado)')

    certificados_trabajo = fields.Binary(string='Certificados de trabajos anteriores', attachment=True)
    certificados_trabajo_filename = fields.Char(string='Archivo certificados')

    planilla_servicios = fields.Binary(string='Planilla de servicios básicos', attachment=True, required=True)
    planilla_servicios_filename = fields.Char(string='Archivo planilla', required=True)

    croquis_domicilio = fields.Binary(string='Croquis del domicilio', attachment=True, required=True)
    croquis_domicilio_filename = fields.Char(string='Archivo croquis', required=True)

    formulario_107 = fields.Binary(string='Formulario No. 107 del SRI', attachment=True)
    formulario_107_filename = fields.Char(string='Archivo formulario 107')

    cuenta_banco_internacional = fields.Binary(string='Cuenta de ahorros Banco Internacional', attachment=True, required=True)
    cuenta_banco_internacional_filename = fields.Char(string='Archivo cuenta bancaria', required=True)

    certificado_salud = fields.Binary(string='Certificado de salud MSP', attachment=True, required=True)
    certificado_salud_filename = fields.Char(string='Archivo certificado salud', required=True)

    recommendation_ids = fields.One2many(
        'applicant.documentation.recommendation',
        'documentation_id',
        string='Recomendaciones',
        copy=False,
    )
    recommendation_count = fields.Integer(
        string='Cantidad de recomendaciones',
        compute='_compute_recommendation_count',
    )

    required_document_total = fields.Integer(
        string='Documentos obligatorios',
        compute='_compute_required_document_summary',
        store=True,
    )
    required_document_uploaded = fields.Integer(
        string='Documentos obligatorios cargados',
        compute='_compute_required_document_summary',
        store=True,
    )
    required_document_missing = fields.Integer(
        string='Documentos obligatorios faltantes',
        compute='_compute_required_document_summary',
        store=True,
    )
    is_complete = fields.Boolean(string='Documentación completa', compute='_compute_is_complete', store=True)

    _sql_constraints = [
        (
            'applicant_documentation_unique',
            'unique(applicant_id)',
            'Solo puede existir un registro de documentación por postulación.',
        ),
    ]

    @api.depends('recommendation_ids', 'recomendaciones', 'cedula_votacion', 'cedula_votacion_2', *[field for field, _, _ in DOCUMENT_FIELDS if field not in OPTIONAL_DOCUMENT_FIELDS and field not in {'recomendaciones', 'cedula_votacion'}])
    def _compute_is_complete(self):
        for record in self:
            required_fields = [
                field for field, _, _ in DOCUMENT_FIELDS
                if field not in OPTIONAL_DOCUMENT_FIELDS and field not in {'recomendaciones', 'cedula_votacion'}
            ]
            recommendation_total = len(record.recommendation_ids) + (1 if record.recomendaciones else 0)
            cedula_total = int(bool(record.cedula_votacion)) + int(bool(record.cedula_votacion_2))
            record.is_complete = all(bool(record[field]) for field in required_fields) and cedula_total >= 2 and recommendation_total >= 2

    @api.depends('recommendation_ids', 'recomendaciones', 'fotografia', 'cedula_votacion', 'cedula_votacion_2', 'hoja_vida_actualizada', 'planilla_servicios', 'croquis_domicilio', 'cuenta_banco_internacional', 'certificado_salud')
    def _compute_required_document_summary(self):
        for record in self:
            total = 10
            uploaded = sum([
                int(bool(record.fotografia)),
                int(bool(record.cedula_votacion)),
                int(bool(record.cedula_votacion_2)),
                int(bool(record.hoja_vida_actualizada)),
                min(len(record.recommendation_ids) + int(bool(record.recomendaciones)), 2),
                int(bool(record.planilla_servicios)),
                int(bool(record.croquis_domicilio)),
                int(bool(record.cuenta_banco_internacional)),
                int(bool(record.certificado_salud)),
            ])
            record.required_document_total = total
            record.required_document_uploaded = uploaded
            record.required_document_missing = max(total - uploaded, 0)

    @api.depends('recommendation_ids', 'recomendaciones')
    def _compute_recommendation_count(self):
        for record in self:
            record.recommendation_count = len(record.recommendation_ids) + (1 if record.recomendaciones else 0)

    @api.constrains(*[f'{field}_filename' for field, _, _ in DOCUMENT_FIELDS if field != 'recomendaciones'], 'cedula_votacion_filename_2')
    def _check_filenames(self):
        for record in self:
            for field, label, file_type in DOCUMENT_FIELDS:
                if field == 'recomendaciones':
                    continue
                filename_field = f'{field}_filename'
                filename = (record[filename_field] or '').lower().strip()
                if not filename:
                    continue
                if file_type == 'pdf' and not filename.endswith('.pdf'):
                    raise ValidationError(_('El documento "%s" debe estar en formato PDF.') % label)
                if file_type == 'image' and not filename.endswith(('.jpg', '.jpeg', '.png', '.pdf')):
                    raise ValidationError(_('La "%s" debe estar en JPG, PNG o PDF.') % label)
            filename_2 = (record.cedula_votacion_filename_2 or '').lower().strip()
            if filename_2 and not filename_2.endswith('.pdf'):
                raise ValidationError(_('La segunda copia de cédula / certificado de votación debe estar en formato PDF.'))

    def _check_pdf_content(self, values):
        for field, label, file_type in DOCUMENT_FIELDS:
            if field == 'recomendaciones' or file_type != 'pdf' or not values.get(field):
                continue
            filename = (values.get(f'{field}_filename') or '').lower()
            if not filename.endswith('.pdf'):
                continue
            try:
                raw = base64.b64decode(values[field])
            except Exception:
                raise ValidationError(_('No se pudo leer el archivo de "%s".') % label)
            if not raw.startswith(b'%PDF'):
                raise ValidationError(_('El archivo de "%s" no parece ser un PDF válido.') % label)
        second_content = values.get('cedula_votacion_2')
        if second_content:
            filename = (values.get('cedula_votacion_filename_2') or '').lower()
            if filename.endswith('.pdf'):
                try:
                    raw = base64.b64decode(second_content)
                except Exception:
                    raise ValidationError(_('No se pudo leer el segundo archivo de cédula / votación.'))
                if not raw.startswith(b'%PDF'):
                    raise ValidationError(_('El segundo archivo de cédula / votación no parece ser un PDF válido.'))
        return True

    @api.model_create_multi
    def create(self, vals_list):
        for values in vals_list:
            self._check_pdf_content(values)
        return super().create(vals_list)

    def write(self, vals):
        self._check_pdf_content(vals)
        return super().write(vals)


class ApplicantDocumentationRecommendation(models.Model):
    _name = 'applicant.documentation.recommendation'
    _description = 'Recomendación de ingreso del postulante'
    _order = 'create_date asc, id asc'

    documentation_id = fields.Many2one(
        'applicant.documentation',
        string='Documentación de ingreso',
        required=True,
        ondelete='cascade',
        index=True,
    )
    archivo = fields.Binary(string='Archivo', attachment=True, required=True)
    filename = fields.Char(string='Archivo', required=True)
    create_date = fields.Datetime(readonly=True)

    @api.constrains('filename')
    def _check_filename(self):
        for record in self:
            if record.filename and not record.filename.lower().endswith('.pdf'):
                raise ValidationError(_('Cada recomendación debe estar en formato PDF.'))

    @api.model_create_multi
    def create(self, vals_list):
        for values in vals_list:
            if values.get('archivo'):
                try:
                    raw = base64.b64decode(values['archivo'])
                except Exception:
                    raise ValidationError(_('No se pudo leer la recomendación cargada.'))
                if not raw.startswith(b'%PDF'):
                    raise ValidationError(_('La recomendación "%s" no parece ser un PDF válido.') % (values.get('filename') or ''))
        return super().create(vals_list)

    def write(self, vals):
        if vals.get('archivo'):
            try:
                raw = base64.b64decode(vals['archivo'])
            except Exception:
                raise ValidationError(_('No se pudo leer la recomendación cargada.'))
            if not raw.startswith(b'%PDF'):
                raise ValidationError(_('La recomendación no parece ser un PDF válido.'))
        return super().write(vals)
