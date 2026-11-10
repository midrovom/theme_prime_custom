# -*- coding: utf-8 -*-
"""Actas: entrega original para empleado y firmas colectivas para departamento.

Devolución de empleado: transferencia a empleado-bodega con receptor e historial.
Devolución de departamento: firma y receptor del departamento, SIN transferencia.
"""
from markupsafe import escape

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class MaintenanceReportWizard(models.TransientModel):
    _inherit = 'maintenance.report.wizard'

    origen_department_id = fields.Many2one(
        'hr.department', string='Departamento actual',
        compute='_compute_origen', readonly=True,
    )
    es_origen_departamento = fields.Boolean(
        compute='_compute_origen', readonly=True,
    )
    origen_empresa_id = fields.Many2one(
        'res.company', string='Empresa del equipo',
        compute='_compute_origen', readonly=True,
    )
    empleado_actual_id = fields.Many2one(
        'hr.employee', string='Empleado actual',
        domain="[('department_id', '=', origen_department_id), "
               "('es_bodega', '=', False), '|', "
               "('company_id', '=', False), ('company_id', '=', origen_empresa_id)]",
        help='Si el equipo es de un departamento, seleccione el colaborador que '
             'realiza la devolución. Para equipos de empleado se mantiene el '
             'empleado asignado sin permitir modificarlo.',
    )
    bodega_employee_id = fields.Many2one(
        'hr.employee', string='Bodega de devolución',
        domain="[('es_bodega', '=', True), '|', ('company_id', '=', False), "
               "('company_id', '=', origen_empresa_id)]",
        help='Solo requerido en devoluciones de equipos asignados a empleados.',
    )
    bodega_department_id = fields.Many2one(
        'hr.department', string='Departamento de bodega',
        compute='_compute_bodega_department', readonly=True,
    )
    receptor_department_ids = fields.Many2many(
        'hr.department', string='Departamentos habilitados para recepción',
        compute='_compute_receptor_departments', readonly=True,
        help='Para empleados: departamento de la bodega elegida. Para equipos '
             'departamentales: departamentos que tengan empleados marcados '
             'Es bodega, sin necesidad de seleccionar una bodega de destino.',
    )
    bodega_receptor_id = fields.Many2one(
        'hr.employee', string='Equipo entregado a (empleado)',
        domain="[('department_id', 'in', receptor_department_ids), "
               "('es_bodega', '=', False), ('id', '!=', bodega_employee_id), "
               "'|', ('company_id', '=', False), "
               "('company_id', '=', origen_empresa_id)]",
        help='En devolución de empleado, receptor del departamento de la '
             'bodega. En devolución departamental, receptor de uno de los '
             'departamentos con bodega habilitada, sin cambiar la asignación.',
    )

    @staticmethod
    def _origin_keys(equipments):
        """Cada acta de devolución tiene un solo tipo y responsable de origen."""
        return set(
            ('department', eq.department_id.id)
            if eq.equipment_assign_to == 'department' and eq.department_id
            else ('employee', eq.employee_id.id)
            if eq.equipment_assign_to == 'employee' and eq.employee_id
            else ('empty', False)
            for eq in equipments
        )

    @api.depends('equipment_ids', 'equipment_ids.equipment_assign_to',
                 'equipment_ids.department_id', 'equipment_ids.employee_id',
                 'equipment_ids.company_id')
    def _compute_origen(self):
        for wizard in self:
            equipments = wizard.equipment_ids
            companies = equipments.mapped('company_id') or self.env.company
            wizard.origen_empresa_id = companies[:1] if len(companies) == 1 else False
            keys = self._origin_keys(equipments)
            is_dept = len(keys) == 1 and next(iter(keys), (None, None))[0] == 'department'
            wizard.es_origen_departamento = bool(is_dept)
            wizard.origen_department_id = equipments[0].department_id if is_dept else False

    @api.depends('bodega_employee_id', 'bodega_employee_id.department_id')
    def _compute_bodega_department(self):
        for wizard in self:
            wizard.bodega_department_id = wizard.bodega_employee_id.department_id

    @api.depends('es_origen_departamento', 'origen_empresa_id',
                 'bodega_department_id')
    def _compute_receptor_departments(self):
        for wizard in self:
            if wizard.es_origen_departamento:
                company = wizard.origen_empresa_id
                if not company:
                    wizard.receptor_department_ids = False
                    continue
                # Sin elegir bodega: reunir departamentos de empleados que
                # tengan marcada Es bodega dentro de la empresa del equipo.
                warehouses = self.env['hr.employee'].sudo().search([
                    ('es_bodega', '=', True),
                    ('department_id', '!=', False),
                    '|', ('company_id', '=', False), ('company_id', '=', company.id),
                ])
                wizard.receptor_department_ids = warehouses.mapped('department_id').filtered(
                    lambda dep: not dep.company_id or dep.company_id == company
                )
            else:
                wizard.receptor_department_ids = wizard.bodega_department_id

    @api.model
    def default_get(self, field_names):
        values = super().default_get(field_names)
        if self.env.context.get('default_report_type') != 'return':
            return values
        commands = self.env.context.get('default_equipment_ids') or []
        ids = []
        for command in commands:
            if isinstance(command, (tuple, list)) and command:
                if command[0] == 6:
                    ids = command[2]
                elif command[0] == 4:
                    ids.append(command[1])
        if not ids and self.env.context.get('active_model') == 'maintenance.equipment':
            ids = self.env.context.get('active_ids') or []
        equipments = self.env['maintenance.equipment'].browse(ids).exists()
        keys = self._origin_keys(equipments)
        if (len(keys) == 1 and equipments and
                next(iter(keys))[0] == 'employee' and
                'empleado_actual_id' in field_names):
            values['empleado_actual_id'] = equipments[0].employee_id.id
        return values

    @api.onchange('equipment_ids')
    def _onchange_equipment_ids_return(self):
        keys = self._origin_keys(self.equipment_ids)
        if len(keys) == 1 and self.equipment_ids and next(iter(keys))[0] == 'employee':
            self.empleado_actual_id = self.equipment_ids[0].employee_id
        else:
            self.empleado_actual_id = False
        self.bodega_employee_id = False
        self.bodega_receptor_id = False

    @api.onchange('bodega_employee_id')
    def _onchange_bodega_employee_id_return(self):
        self.bodega_receptor_id = False

    def _check_return_source(self, equipments):
        keys = self._origin_keys(equipments)
        if len(keys) != 1 or next(iter(keys), ('empty', False))[0] == 'empty':
            raise UserError(_(
                'Para devolver equipos conjuntamente, seleccione equipos '
                'del mismo departamento o asignados al mismo empleado. '
                'No mezcle orígenes distintos.'
            ))
        kind, record_id = next(iter(keys))
        employee = self.empleado_actual_id
        if not employee or not employee.exists():
            raise UserError(_('Seleccione el empleado que realiza la devolución.'))
        if kind == 'department':
            department = self.env['hr.department'].browse(record_id)
            if employee.department_id != department:
                raise UserError(_(
                    'El empleado que devuelve debe pertenecer al departamento "%s".'
                ) % department.display_name)
        elif employee.id != record_id:
            raise UserError(_(
                'El empleado actual debe ser el mismo empleado asignado a los equipos.'
            ))
        companies = {(eq.company_id or self.env.company).id for eq in equipments}
        if len(companies) != 1:
            raise UserError(_('Los equipos seleccionados deben pertenecer a una sola empresa.'))
        company_id = next(iter(companies))
        if employee.company_id and employee.company_id.id != company_id:
            raise UserError(_('El empleado que devuelve pertenece a otra empresa.'))
        if employee.es_bodega:
            raise UserError(_(
                'El empleado que devuelve no puede tener marcada la casilla "Es bodega".'
            ))
        return kind, company_id

    def _check_department_receiver(self, equipments, company_id):
        """Validar receptor departamental también en servidor (no solo dominio)."""
        receiver = self.bodega_receptor_id
        department = equipments[0].department_id
        if not department:
            raise UserError(_('Los equipos necesitan un departamento de origen.'))
        if not receiver or not receiver.exists():
            raise UserError(_('Seleccione el empleado que recibe el equipo del departamento.'))
        if receiver.es_bodega:
            raise UserError(_(
                'Equipo entregado a no puede ser un empleado con "Es bodega".'
            ))
        # En modo Departamento el receptor puede ser de Sistemas, RRHH u
        # otro departamento con bodega configurada; no necesariamente del
        # mismo departamento al que está asignado el equipo.
        warehouse_in_receiver_department = self.env['hr.employee'].sudo().search([
            ('es_bodega', '=', True),
            ('department_id', '=', receiver.department_id.id if receiver.department_id else False),
            '|', ('company_id', '=', False), ('company_id', '=', company_id),
        ], limit=1)
        if not warehouse_in_receiver_department:
            raise UserError(_(
                'El empleado receptor debe pertenecer a un departamento con '
                'al menos un empleado marcado "Es bodega" (Sistemas, RRHH, etc.).'
            ))
        if (receiver.department_id.company_id and
                receiver.department_id.company_id.id != company_id):
            raise UserError(_('El departamento del receptor pertenece a otra empresa.'))
        if receiver.company_id and receiver.company_id.id != company_id:
            raise UserError(_('El receptor pertenece a otra empresa.'))
        if department.company_id and department.company_id.id != company_id:
            raise UserError(_('El departamento pertenece a otra empresa.'))
        if self.bodega_employee_id:
            # Un cliente RPC no debe poder ocultar una bodega en un movimiento
            # departamental que, por definición, no tiene transferencia a bodega.
            raise UserError(_(
                'Para equipos de departamento no seleccione Bodega de devolución.'
            ))
        return department, receiver

    def _register_department_return(self, equipments, company_id):
        """Registrar el movimiento SIN escribir employee_id ni department_id."""
        department, receiver = self._check_department_receiver(equipments, company_id)
        employee = self.empleado_actual_id
        operator = self.env.user
        now = fields.Datetime.now()
        History = self.env['maintenance.equipment.bodega.history'].sudo()
        for equipment in equipments:
            # El último receptor del mismo departamento receptor permite ver
            # la cadena histórica; ninguna entrada previa se sobrescribe.
            previous = History.search([
                ('equipment_id', '=', equipment.id),
                ('movement_type', '=', 'department_return'),
                ('destination_department_id', '=', receiver.department_id.id),
            ], limit=1)
            previous_receiver = previous.receiver_employee_id if previous else False
            equipment.write({
                'devolucion_acta_empleado_id': employee.id,
                'devolucion_acta_departamento_id': department.id,
                'devolucion_acta_receptor_id': receiver.id,
                'entregado_por_id': self.entregado_por_id.id,
            })
            History.create({
                'equipment_id': equipment.id,
                'company_id': company_id,
                'movement_type': 'department_return',
                'movement_date': now,
                'previous_employee_id': employee.id,
                'previous_department_id': department.id,
                'destination_department_id': receiver.department_id.id,
                'warehouse_employee_id': False,
                'receiver_employee_id': receiver.id,
                'previous_receiver_employee_id': previous_receiver.id if previous_receiver else False,
                'registered_by_id': operator.id,
                'previous_employee_name': employee.display_name,
                'previous_department_name': department.display_name,
                'warehouse_name': False,
                'receiver_name': receiver.display_name,
                'previous_receiver_name': previous_receiver.display_name if previous_receiver else False,
                'registered_by_name': operator.display_name,
            })
            equipment.message_post(
                body=_('Devolución del departamento %(department)s: '
                       '%(employee)s entregó el equipo a %(receiver)s. '
                       'Receptor del departamento %(destination)s. '
                       'Sin cambio de asignación ni envío a bodega. '
                       'Registrado por %(operator)s.') % {
                    'department': escape(department.display_name),
                    'employee': escape(employee.display_name),
                    'receiver': escape(receiver.display_name),
                    'destination': escape(receiver.department_id.display_name),
                    'operator': escape(operator.display_name),
                },
                subtype_xmlid='mail.mt_note',
            )

    def action_generate_report(self):
        self.ensure_one()
        if self.report_type != 'return':
            # Entrega individual y uniforme conservan la lógica de los addons
            # originales. Solo la entrega departamental imprime varias firmas.
            if self.report_type == 'delivery' and self.equipment_ids:
                dept_equipments = self.equipment_ids.filtered(
                    lambda eq: eq.equipment_assign_to == 'department' and eq.department_id
                )
                if dept_equipments:
                    dept_ids = set(self.equipment_ids.mapped('department_id').ids)
                    if len(dept_equipments) != len(self.equipment_ids) or len(dept_ids) != 1:
                        raise UserError(_(
                            'Para un acta de entrega departamental, seleccione '
                            'únicamente equipos del mismo departamento.'
                        ))
                    if not dept_equipments[0]._get_department_delivery_signers():
                        raise UserError(_(
                            'El departamento "%s" no tiene empleados activos para firmar.'
                        ) % dept_equipments[0].department_id.display_name)
            return super().action_generate_report()

        equipments = self.equipment_ids.exists()
        if not equipments:
            raise UserError(_('Debe seleccionar al menos un equipo.'))
        kind, company_id = self._check_return_source(equipments)
        if not self.entregado_por_id:
            raise UserError(_('Seleccione el encargado de entrega/recepción de equipos.'))

        if kind == 'department':
            # El equipo sigue asignado al departamento. Solo cambia el
            # historial/auditoría y el firmante de esta acta.
            self._register_department_return(equipments, company_id)
        else:
            # Comportamiento heredado del antiguo botón Asignar a bodega.
            if not self.bodega_employee_id or not self.bodega_receptor_id:
                raise UserError(_(
                    'Seleccione la Bodega de devolución y su empleado receptor.'
                ))
            assignment = self.env['maintenance.equipment.bodega.wizard'].create({
                'equipment_ids': [(6, 0, equipments.ids)],
                'company_id': company_id,
                'bodega_employee_id': self.bodega_employee_id.id,
                'bodega_receptor_id': self.bodega_receptor_id.id,
            })
            assignment._apply_assignment(return_employee=self.empleado_actual_id)
            equipments.write({
                'devolucion_acta_empleado_id': self.empleado_actual_id.id,
                'devolucion_acta_departamento_id': False,
                'devolucion_acta_receptor_id': self.bodega_receptor_id.id,
                'entregado_por_id': self.entregado_por_id.id,
            })
        return self.env.ref(
            'maintenance_report.maintenance_equipment_return_report'
        ).report_action(equipments)
