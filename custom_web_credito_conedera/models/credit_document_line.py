import base64
import binascii

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ConederaCreditDocumentLine(models.Model):
    _name = 'conedera.credit.document.line'
    _description = 'Archivo de requisito documental de crédito'
    _order = 'requirement_id, id'

    document_id = fields.Many2one('conedera.credit.documents', string='Expediente', required=True, ondelete='cascade', index=True)
    application_id = fields.Many2one(related='document_id.application_id', store=True, readonly=True, string='Solicitud')
    applicant_type_id = fields.Many2one(related='document_id.applicant_type_id', string='Tipo de solicitante', store=True, readonly=True, index=True)
    requirement_id = fields.Many2one('conedera.credit.document.requirement', string='Documento requerido', required=True, ondelete='restrict', index=True)
    name = fields.Char(related='requirement_id.name', string='Documento', readonly=True)
    file = fields.Binary(string='Archivo', attachment=True)
    filename = fields.Char(string='Nombre de archivo')
    uploaded_at = fields.Datetime(string='Fecha de carga', readonly=True)

    @api.model
    def init(self):
        # La versión previa solo permitía un archivo por requisito. No eliminar filas.
        self.env.cr.execute("""
            ALTER TABLE IF EXISTS conedera_credit_document_line
            DROP CONSTRAINT IF EXISTS conedera_credit_document_line_credit_document_line_unique
        """)

    @api.constrains('requirement_id', 'document_id')
    def _check_requirement_type(self):
        for rec in self:
            if rec.requirement_id.applicant_type_id != rec.document_id.application_id.applicant_type_id:
                raise ValidationError(_('El documento solicitado no corresponde al tipo de solicitante de esta solicitud.'))

    @api.model
    def _validate_file(self, requirement, filename, content):
        if not filename or not content:
            return
        filename = filename.lower().strip()
        allowed = ('.pdf',) if requirement.pdf_only else (('.jpg', '.jpeg', '.png') if requirement.image_only else ('.pdf', '.jpg', '.jpeg', '.png'))
        if not filename.endswith(allowed):
            raise ValidationError(_('Formato no permitido para "%s". Permitidos: %s.') % (requirement.name, ', '.join(allowed)))
        try:
            decoded = base64.b64decode(content, validate=True)
        except (ValueError, binascii.Error, TypeError):
            raise ValidationError(_('Archivo incorrecto para "%s".') % requirement.name)
        if len(decoded) > 12 * 1024 * 1024:
            raise ValidationError(_('El archivo "%s" supera 12 MB.') % requirement.name)
        if filename.endswith('.pdf'):
            correct = decoded.startswith(b'%PDF')
        elif filename.endswith(('.jpg', '.jpeg')):
            correct = decoded.startswith(b'\xff\xd8\xff')
        else:
            correct = decoded.startswith(b'\x89PNG\r\n\x1a\n')
        if not correct:
            raise ValidationError(_('El contenido del archivo "%s" no coincide con su extensión.') % requirement.name)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('file'):
                requirement = self.env['conedera.credit.document.requirement'].browse(vals['requirement_id'])
                self._validate_file(requirement, vals.get('filename'), vals['file'])
                vals.setdefault('uploaded_at', fields.Datetime.now())
        return super().create(vals_list)

    def write(self, vals):
        if vals.get('file'):
            for record in self:
                record._validate_file(record.requirement_id, vals.get('filename', record.filename), vals['file'])
            vals = dict(vals, uploaded_at=fields.Datetime.now())
        return super().write(vals)
