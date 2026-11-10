# -*- coding: utf-8 -*-
from markupsafe import escape
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class MaintenanceEquipmentBodegaWizard(models.TransientModel):
    _name = 'maintenance.equipment.bodega.wizard'
    _description = 'Asignación individual o masiva de equipos a bodega'

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
        help='Solo empleados con la casilla Es bodega.',
    )
    bodega_department_id = fields.Many2one(
        'hr.department', string='Departamento de la bodega',
        compute='_compute_bodega_department_id', readonly=True,
    )
    bodega_receptor_id = fields.Many2one(
        'hr.employee', string='Equipo entregado a (empleado)', required=True,
        domain="[('department_id', '=', bodega_department_id), ('es_bodega', '=', False), ('id', '!=', bodega_employee_id), '|', ('company_id', '=', False), ('company_id', '=', company_id)]",
        help='Empleado que recibió físicamente los equipos. Solo aparecen empleados del departamento de la bodega que NO tengan marcada la casilla Es bodega. El equipo queda asignado a la bodega.',
    )

    @api.depends('equipment_ids', 'equipment_id')
    def _compute_equipment_count(self):
        for wizard in self:
            wizard.equipment_count = len(wizard.equipment_ids) or (1 if wizard.equipment_id else 0)

    @api.depends('bodega_employee_id', 'bodega_employee_id.department_id')
    def _compute_bodega_department_id(self):
        for wizard in self:
            wizard.bodega_department_id = wizard.bodega_employee_id.department_id

    @api.onchange('bodega_employee_id')
    def _onchange_bodega_employee_id(self):
        # Evitar que quede una persona de un departamento distinto cuando el
        # usuario cambia la bodega antes de confirmar.
        self.bodega_receptor_id = False

    def action_confirm_assignment(self):
        self.ensure_one()
        equipment_set = self.equipment_ids or self.equipment_id
        if not equipment_set:
            raise UserError(_('No se han seleccionado equipos para la asignación.'))
        if len(equipment_set.exists()) != len(equipment_set):
            raise UserError(_('Uno de los equipos seleccionados ya no existe.'))

        destination = self.bodega_employee_id
        receiver = self.bodega_receptor_id
        if not destination or not destination.exists() or not destination.es_bodega:
            raise UserError(_('Seleccione un empleado con la casilla "Es bodega".'))
        if not destination.department_id:
            raise UserError(_(
                'La bodega "%s" no tiene departamento. Asígnele un departamento '
                'en Empleados antes de registrar la entrega.'
            ) % destination.display_name)
        if not receiver or not receiver.exists():
            raise UserError(_('Seleccione al empleado que recibió el equipo en la bodega.'))
        # También validar en servidor: una bodega no puede figurar como receptor,
        # aunque se haya enviado el ID mediante RPC o una vista personalizada.
        if receiver.es_bodega or receiver == destination:
            raise UserError(_(
                'El empleado receptor no puede tener marcada la casilla "Es bodega". '
                'Seleccione otro empleado del departamento de la bodega.'
            ))
        if receiver.department_id != destination.department_id:
            raise UserError(_(
                'El empleado receptor debe pertenecer al departamento "%s" de la bodega.'
            ) % destination.department_id.display_name)

        # Validaciones del lado servidor: no basta con el dominio de la vista.
        # Validar toda la selección ANTES de realizar cualquier escritura.
        company_ids = {(eq.company_id or self.env.company).id for eq in equipment_set}
        if len(company_ids) != 1 or self.company_id.id not in company_ids:
            raise UserError(_('Los equipos deben pertenecer a la misma empresa.'))

        company = self.env['res.company'].browse(next(iter(company_ids)))
        for employee, label in ((destination, _('bodega')), (receiver, _('empleado receptor'))):
            if employee.company_id and employee.company_id != company:
                raise UserError(_(
                    'El %(label)s "%(employee)s" debe pertenecer a la empresa "%(company)s".'
                ) % {
                    'label': label,
                    'employee': employee.display_name,
                    'company': company.display_name,
                })
        if destination.department_id.company_id and destination.department_id.company_id != company:
            raise UserError(_(
                'El departamento de la bodega debe pertenecer a la empresa de los equipos.'
            ))

        # Si ya está en esa bodega, sí se permite registrar una NUEVA entrega
        # cuando cambie la persona que recibe. Si es el mismo receptor, omitir.
        to_change = equipment_set.filtered(
            lambda eq: eq.employee_id != destination or eq.bodega_receptor_ultimo_id != receiver
        )
        if not to_change:
            raise UserError(_(
                'Todos los equipos ya están asignados a esa bodega y registrados '
                'con el mismo empleado receptor.'
            ))

        user = self.env.user
        now = fields.Datetime.now()
        History = self.env['maintenance.equipment.bodega.history'].sudo()
        for equipment in to_change:
            previous = equipment.employee_id
            same_bodega = previous == destination
            previous_receiver = equipment.bodega_receptor_ultimo_id if same_bodega else False
            # Al cambiar solo el receptor dentro de la misma bodega se conserva
            # el empleado original, importante para el acta de devolución.
            original_employee = (
                equipment.empleado_devolucion_anterior_id if same_bodega else previous
            )
            equipment.write({
                'empleado_devolucion_anterior_id': original_employee.id if original_employee else False,
                'employee_id': destination.id,
                'equipment_assign_to': 'employee',
                'department_id': False,
                'bodega_destino_ultima_id': destination.id,
                'bodega_receptor_ultimo_id': receiver.id,
                'bodega_asignado_por_id': user.id,
                'bodega_asignacion_fecha': now,
            })
            # Cada equipo tiene su propio registro, incluso en asignación
            # masiva. Solo guardar datos validados después de equipment.write.
            History.create({
                'equipment_id': equipment.id,
                'company_id': company.id,
                'movement_date': now,
                'previous_employee_id': previous.id if previous else False,
                'warehouse_employee_id': destination.id,
                'receiver_employee_id': receiver.id,
                'previous_receiver_employee_id': previous_receiver.id if previous_receiver else False,
                'registered_by_id': user.id,
                'previous_employee_name': previous.display_name if previous else _('Sin empleado'),
                'warehouse_name': destination.display_name,
                'receiver_name': receiver.display_name,
                'previous_receiver_name': previous_receiver.display_name if previous_receiver else False,
                'registered_by_name': user.display_name,
            })
            equipment.message_post(
                body=_('Movimiento a bodega: %(old)s → %(warehouse)s. '
                       'Recibido por %(receiver)s. %(previous_receiver)s'
                       'Registrado por %(user)s.') % {
                    'old': escape(previous.display_name if previous else _('Sin empleado')),
                    'warehouse': escape(destination.display_name),
                    'receiver': escape(receiver.display_name),
                    'previous_receiver': (
                        _('Receptor anterior: %s. ') % escape(previous_receiver.display_name)
                        if previous_receiver else ''
                    ),
                    'user': escape(user.display_name),
                },
                subtype_xmlid='mail.mt_note',
            )

        return {'type': 'ir.actions.client', 'tag': 'reload'}
