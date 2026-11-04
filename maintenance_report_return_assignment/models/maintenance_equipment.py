# -*- coding: utf-8 -*-
from odoo import fields, models


class MaintenanceEquipment(models.Model):
    _inherit = 'maintenance.equipment'

    # Snapshot of the employee who returned the equipment.  This keeps the
    # PDF accurate after employee_id is changed to the receiving employee.
    empleado_devolucion_anterior_id = fields.Many2one(
        'hr.employee',
        string='Empleado que devolvió el equipo',
        copy=False,
        readonly=True,
        tracking=True,
        help='Empleado asignado antes de la última acta de devolución.',
    )
