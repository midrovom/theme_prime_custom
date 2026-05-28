from odoo import models, fields

class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    document_ids = fields.One2many(
        'hr.employee.document',  # modelo relacionado
        'employee_id',           # campo inverso
        string='Documentos'
    )

class HrEmployeeDocument(models.Model):
    _name = 'hr.employee.document'
    _description = 'Documentos del empleado'

    name = fields.Char(string='Nombre del documento', required=True)
    file = fields.Binary(string='Archivo')
    employee_id = fields.Many2one('hr.employee', string='Empleado', ondelete='cascade')
