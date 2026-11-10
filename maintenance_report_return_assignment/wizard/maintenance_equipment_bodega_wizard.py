# -*- coding: utf-8 -*-
from markupsafe import escape
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class MaintenanceEquipmentBodegaWizard(models.TransientModel):
    _name = 'maintenance.equipment.bodega.wizard'
    _description = 'Asignación individual o masiva de equipos a bodega'

    # Compatibilidad con el popup de versiones anteriores (18.0.1.6.0).
    equipment_id = fields.Many2one(
        'maintenance.equipment', string='Equipo', readonly=True,
    )
    equipment_ids = fields.Many2many(
        'maintenance.equipment',
        'maintenance_bodega_wizard_equipment_rel',
        'wizard_id', 'equipment_id',
        string='Equipos seleccionados', readonly=True,
    )
    equipment_count = fields.Integer(
        string='Cantidad de equipos', compute='_compute_equipment_count',
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

    @api.depends('equipment_ids', 'equipment_id')
    def _compute_equipment_count(self):
        for wizard in self:
            wizard.equipment_count = len(wizard.equipment_ids) or (1 if wizard.equipment_id else 0)

    def action_confirm_assignment(self):
        self.ensure_one()
        equipment_set = self.equipment_ids or self.equipment_id
        if not equipment_set:
            raise UserError(_('No se han seleccionado equipos para la asignación.'))
        if len(equipment_set.exists()) != len(equipment_set):
            raise UserError(_('Uno de los equipos seleccionados ya no existe.'))

        destination = self.bodega_employee_id
        if not destination or not destination.exists() or not destination.es_bodega:
            raise UserError(_(
                'Seleccione un empleado que tenga marcada la casilla "Es bodega".'
            ))

        # Repetir las validaciones en servidor, sin depender del domain del
        # cliente. No comenzar a escribir hasta validar toda la selección.
        company_ids = {(eq.company_id or self.env.company).id for eq in equipment_set}
        if len(company_ids) != 1 or self.company_id.id not in company_ids:
            raise UserError(_('Los equipos deben pertenecer a la misma empresa.'))
        for equipment in equipment_set:
            if (equipment.company_id and destination.company_id
                    and equipment.company_id != destination.company_id):
                raise UserError(_(
                    'La bodega seleccionada debe pertenecer a la misma empresa que el equipo "%s".'
                ) % equipment.display_name)
        if destination.company_id and destination.company_id.id not in company_ids:
            raise UserError(_('La bodega seleccionada debe pertenecer a la empresa de los equipos.'))

        to_change = equipment_set.filtered(lambda eq: eq.employee_id != destination)
        if not to_change:
            raise UserError(_('Todos los equipos seleccionados ya están asignados a esa bodega.'))

        # Cada equipo puede tener un empleado anterior diferente. Grabar
        # individualmente evita que la auditoría se sobrescriba con el de otro.
        user = self.env.user
        now = fields.Datetime.now()
        for equipment in to_change:
            previous = equipment.employee_id
            equipment.write({
                'empleado_devolucion_anterior_id': previous.id or False,
                'employee_id': destination.id,
                'equipment_assign_to': 'employee',
                'department_id': False,
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
