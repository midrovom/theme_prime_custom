from odoo import models, fields

class MaintenanceEquipment(models.Model):
    _inherit = 'maintenance.equipment'

    entregado_por_id = fields.Many2one('hr.employee', string='Responsable de Entrega', tracking=True)


class Department(models.Model):
    _inherit = "hr.department"

    responsable_entrega_equipo = fields.Boolean( string="Responsable de entrega de equipo",
        help="Marcar si este departamento es responsable de la entrega de equipos."
    )
