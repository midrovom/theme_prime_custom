from odoo import models, fields, api

class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    document_ids = fields.One2many('hr.employee.document', 'employee_id', string='Documentos')
    is_readonly_group = fields.Boolean(compute='_compute_is_readonly_group', store=False)

    @api.depends_context('uid')
    def _compute_is_readonly_group(self):
        for rec in self:
            rec.is_readonly_group = self.env.user.has_group(
                'tu_modulo.group_attachment_hr_readonly_custom'
            )

class HrEmployeeDocument(models.Model):
    _name = 'hr.employee.document'
    _description = 'Documentos del empleado'

    name = fields.Char(string='Nombre del documento', required=True)
    file = fields.Binary(string='Archivo')
    employee_id = fields.Many2one('hr.employee', string='Empleado', ondelete='cascade')

