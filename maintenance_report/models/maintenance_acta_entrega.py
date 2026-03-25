from odoo import models, fields

class MaintenanceEquipment(models.Model):
    _inherit = 'maintenance.equipment'

    entregado_por_id = fields.Many2one('hr.employee', string='Responsable de Entrega', tracking=True)
