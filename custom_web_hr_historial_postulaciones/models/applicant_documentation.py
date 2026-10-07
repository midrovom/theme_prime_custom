import base64

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


DOCUMENT_FIELDS = [
    ('fotografia', 'Fotografía actualizada a color tamaño carnet', 'image'),
    ('cedula_votacion', '2 copias a color de cédula de identidad y certificado de votación', 'pdf'),
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

    cedula_votacion = fields.Binary(string='Cédula y votación', attachment=True, required=True)
    cedula_votacion_filename = fields.Char(string='Archivo cédula y votación', required=True)

    historia_iess = fields.Binary(string='Historia laboral IESS', attachment=True, required=True)
    historia_iess_filename = fields.Char(string='Archivo historia IESS', required=True)

    acta_matrimonio = fields.Binary(string='Acta de matrimonio / unión de hecho', attachment=True, required=True)
    acta_matrimonio_filename = fields.Char(string='Archivo acta', required=True)

    documentos_hijos = fields.Binary(string='Documentos de hijos menores', attachment=True, required=True)
    documentos_hijos_filename = fields.Char(string='Archivo documentos hijos', required=True)

    estudios_titulo = fields.Binary(string='Estudios / título SENESCYT', attachment=True, required=True)
    estudios_titulo_filename = fields.Char(string='Archivo estudios / título', required=True)

    cursos_realizados = fields.Binary(string='Cursos realizados', attachment=True, required=True)
    cursos_realizados_filename = fields.Char(string='Archivo cursos', required=True)

    recomendaciones = fields.Binary(string='Recomendaciones', attachment=True, required=True)
    recomendaciones_filename = fields.Char(string='Archivo recomendaciones', required=True)

    certificados_trabajo = fields.Binary(string='Certificados de trabajos anteriores', attachment=True, required=True)
    certificados_trabajo_filename = fields.Char(string='Archivo certificados', required=True)

    planilla_servicios = fields.Binary(string='Planilla de servicios básicos', attachment=True, required=True)
    planilla_servicios_filename = fields.Char(string='Archivo planilla', required=True)

    croquis_domicilio = fields.Binary(string='Croquis del domicilio', attachment=True, required=True)
    croquis_domicilio_filename = fields.Char(string='Archivo croquis', required=True)

    formulario_107 = fields.Binary(string='Formulario No. 107 del SRI', attachment=True, required=True)
    formulario_107_filename = fields.Char(string='Archivo formulario 107', required=True)

    cuenta_banco_internacional = fields.Binary(string='Cuenta de ahorros Banco Internacional', attachment=True, required=True)
    cuenta_banco_internacional_filename = fields.Char(string='Archivo cuenta bancaria', required=True)

    certificado_salud = fields.Binary(string='Certificado de salud MSP', attachment=True, required=True)
    certificado_salud_filename = fields.Char(string='Archivo certificado salud', required=True)

    is_complete = fields.Boolean(string='Documentación completa', compute='_compute_is_complete', store=True)

    _sql_constraints = [
        (
            'applicant_documentation_unique',
            'unique(applicant_id)',
            'Solo puede existir un registro de documentación por postulación.',
        ),
    ]

    @api.depends(*[field for field, _, _ in DOCUMENT_FIELDS])
    def _compute_is_complete(self):
        for record in self:
            record.is_complete = all(bool(record[field]) for field, _, _ in DOCUMENT_FIELDS)

    @api.constrains(*[field for field, _, _ in DOCUMENT_FIELDS])
    def _check_required_documents(self):
        for record in self:
            missing = [label for field, label, _ in DOCUMENT_FIELDS if not record[field]]
            if missing:
                raise ValidationError(
                    _('Falta información/documentación obligatoria:\n- %s') % '\n- '.join(missing)
                )

    @api.constrains(*[f'{field}_filename' for field, _, _ in DOCUMENT_FIELDS])
    def _check_filenames(self):
        for record in self:
            for field, label, file_type in DOCUMENT_FIELDS:
                filename_field = f'{field}_filename'
                filename = (record[filename_field] or '').lower().strip()
                if not filename:
                    continue
                if file_type == 'pdf' and not filename.endswith('.pdf'):
                    raise ValidationError(_('El documento "%s" debe estar en formato PDF.') % label)
                if file_type == 'image' and not filename.endswith(('.jpg', '.jpeg', '.png', '.pdf')):
                    raise ValidationError(_('La "%s" debe estar en JPG, PNG o PDF.') % label)

    def _check_pdf_content(self, values):
        """Valida de forma conservadora la firma PDF cuando se está recibiendo un PDF."""
        for field, label, file_type in DOCUMENT_FIELDS:
            if file_type != 'pdf' or not values.get(field):
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
        return True

    @api.model_create_multi
    def create(self, vals_list):
        for values in vals_list:
            self._check_pdf_content(values)
        return super().create(vals_list)

    def write(self, vals):
        self._check_pdf_content(vals)
        return super().write(vals)
