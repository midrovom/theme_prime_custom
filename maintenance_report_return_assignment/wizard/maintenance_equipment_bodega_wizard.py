# -*- coding: utf-8 -*-
from markupsafe import escape
from odoo import _, fields, models
from odoo.exceptions import UserError


class MaintenanceEquipmentBodegaWizard(models.TransientModel):
    _name = 'maintenance.equipment.bodega.wizard'
    _description = 'Asignación de equipo a bodega'

    equipment_id = fields.Many2one(
        'maintenance.equipment', string='Equipo', required=True, readonly=True,
    )
    employee_anterior_id = fields.Many2one(
        'hr.employee', string='Empleado actual',
        related='equipment_id.employee_id', readonly=True,
    )
    company_id = fields.Many2one(
        'res.company', string='Empresa', required=True,
        default=lambda self: self.env.company, readonly=True,
    )
    bodega_employee_id = fields.Many2one(
        'hr.employee', string='Bodega de devolución', required=True,
        domain="[('es_bodega', '=', True), '|', ('company_id', '=', False), ('company_id', '=', company_id)]",
        help='Solo empleados que tienen activada la casilla Es bodega.',
    )

    def action_confirm_assignment(self):
        self.ensure_one()
        equipment = self.equipment_id
        destination = self.bodega_employee_id
        if not equipment.exists():
            raise UserError(_('El equipo ya no existe.'))
        if not destination or not destination.exists() or not destination.es_bodega:
            raise UserError(_(
                'Seleccione un empleado que tenga marcada la casilla "Es bodega".'
            ))
        if equipment.company_id and destination.company_id and equipment.company_id != destination.company_id:
            raise UserError(_(
                'La bodega seleccionada debe pertenecer a la misma empresa que el equipo.'
            ))
        if equipment.employee_id == destination:
            raise UserError(_(
                'Este equipo ya está asignado al empleado "%s".'
            ) % destination.display_name)

        previous = equipment.employee_id
        user = self.env.user
        now = fields.Datetime.now()
        equipment.write({
            'empleado_devolucion_anterior_id': previous.id or False,
            'employee_id': destination.id,
            'bodega_asignado_por_id': user.id,
            'bodega_asignacion_fecha': now,
        })
        equipment.message_post(
            body=_('Asignación a bodega: %(old)s → %(new)s. Registrado por %(user)s.') % {
                'old': escape(previous.display_name if previous else _('Sin empleado')),
                'new': escape(destination.display_name),
                'user': escape(user.display_name),
            },
            subtype_xmlid='mail.mt_note',
        )
        return {'type': 'ir.actions.client', 'tag': 'reload'}
