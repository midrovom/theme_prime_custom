# -*- coding: utf-8 -*-
from odoo import _, fields, models


class MaintenanceEquipment(models.Model):
    _inherit = 'maintenance.equipment'

    # Se conserva el campo de las versiones anteriores, para no perder el
    # origen del equipo y para que el acta pueda mostrar al colaborador.
    empleado_devolucion_anterior_id = fields.Many2one(
        'hr.employee',
        string='Empleado anterior',
        readonly=True,
        copy=False,
        tracking=True,
        help='Empleado que tenía asignado el equipo antes de su última transferencia a bodega.',
    )
    bodega_asignado_por_id = fields.Many2one(
        'res.users',
        string='Registrado por',
        readonly=True,
        copy=False,
        tracking=True,
        help='Usuario de Odoo que realizó la última asignación del equipo a bodega.',
    )
    bodega_asignacion_fecha = fields.Datetime(
        string='Fecha de asignación a bodega',
        readonly=True,
        copy=False,
        tracking=True,
    )

    def action_open_bodega_assignment(self):
        self.ensure_one()
        return {
            'name': _('Asignar equipo a bodega'),
            'type': 'ir.actions.act_window',
            'res_model': 'maintenance.equipment.bodega.wizard',
            'view_mode': 'form',
            'view_id': self.env.ref(
                'maintenance_report_return_assignment.view_maintenance_equipment_bodega_wizard_form'
            ).id,
            'target': 'new',
            'context': {
                'default_equipment_id': self.id,
                'default_company_id': (self.company_id or self.env.company).id,
            },
        }
