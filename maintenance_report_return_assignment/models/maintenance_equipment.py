# -*- coding: utf-8 -*-
from odoo import _, fields, models
from odoo.exceptions import UserError


class MaintenanceEquipment(models.Model):
    _inherit = 'maintenance.equipment'

    # Se conservan los campos existentes de auditoría. En operaciones masivas,
    # estos valores se actualizan por separado en CADA equipo seleccionado.
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
        """Permite abrir el mismo wizard para uno o varios equipos seleccionados.

        Se invoca desde el smart button individual, desde el botón de la
        cabecera de la lista o desde Acción > Asignar a bodega.
        """
        if not self:
            raise UserError(_('Seleccione al menos un equipo para asignar a bodega.'))

        # La selección masiva debe tener una sola empresa para evitar transferir
        # accidentalmente equipos de compañías diferentes a un mismo empleado.
        company_ids = {(equipment.company_id or self.env.company).id for equipment in self}
        if len(company_ids) != 1:
            raise UserError(_(
                'Seleccione equipos de la misma empresa para asignarlos a una bodega. '
                'Si tiene equipos de varias empresas, realice una asignación por empresa.'
            ))

        return {
            'name': _('Asignar equipos a bodega') if len(self) > 1 else _('Asignar equipo a bodega'),
            'type': 'ir.actions.act_window',
            'res_model': 'maintenance.equipment.bodega.wizard',
            'view_mode': 'form',
            'view_id': self.env.ref(
                'maintenance_report_return_assignment.view_maintenance_equipment_bodega_wizard_form'
            ).id,
            'target': 'new',
            'context': {
                'default_equipment_ids': [(6, 0, self.ids)],
                'default_equipment_id': self.id if len(self) == 1 else False,
                'default_company_id': next(iter(company_ids)),
            },
        }
