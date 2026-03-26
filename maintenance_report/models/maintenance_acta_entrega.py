from odoo import models, fields

class MaintenanceEquipment(models.Model):
    _inherit = 'maintenance.equipment'

    entregado_por_id = fields.Many2one('hr.employee', string='Entrega RH', tracking=True)
    enable_model_serial = fields.Boolean(string='Habilitar Modelo/Serial')


class Department(models.Model):
    _inherit = "hr.department"

    responsable_entrega_equipo = fields.Boolean( string="Habilita entrega",
        help="Los empleados de este departamento podrán ser designados como responsables de entrega de equipos."
    )


