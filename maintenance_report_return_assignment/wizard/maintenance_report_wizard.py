# -*- coding: utf-8 -*-
"""Acta de devolución con traspaso a bodega y origen por empleado/departamento.

Entrega y uniforme mantienen su lógica original mediante super().
"""
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
        domain="[('department_id', '=', origen_department_id), '|', "
               "('company_id', '=', False), ('company_id', '=', origen_empresa_id)]",
        help='Si el equipo está asignado a un departamento, elija al empleado de '
             'ese departamento que realiza la devolución. Si está asignado a un '
             'empleado, se conserva automáticamente ese mismo empleado.',
    )
    bodega_employee_id = fields.Many2one(
        'hr.employee', string='Bodega de devolución',
        domain="[('es_bodega', '=', True), '|', ('company_id', '=', False), "
               "('company_id', '=', origen_empresa_id)]",
    )
    bodega_department_id = fields.Many2one(
        'hr.department', string='Departamento de bodega',
        compute='_compute_bodega_department', readonly=True,
    )
    bodega_receptor_id = fields.Many2one(
        'hr.employee', string='Equipo entregado a (empleado)',
        domain="[('department_id', '=', bodega_department_id), "
               "('es_bodega', '=', False), ('id', '!=', bodega_employee_id), "
               "'|', ('company_id', '=', False), "
               "('company_id', '=', origen_empresa_id)]",
    )

    @staticmethod
    def _origin_keys(equipments):
        """Una acta debe corresponder a una sola procedencia y responsable."""
        return set(
            ('department', eq.department_id.id)
            if eq.equipment_assign_to == 'department' and eq.department_id
            else ('employee', eq.employee_id.id)
            if eq.employee_id else ('empty', False)
            for eq in equipments
        )

    @api.depends('equipment_ids', 'equipment_ids.equipment_assign_to',
                 'equipment_ids.department_id', 'equipment_ids.employee_id',
                 'equipment_ids.company_id')
    def _compute_origen(self):
        for wizard in self:
            equipments = wizard.equipment_ids
            companies = (equipments.mapped('company_id') or self.env.company)
            wizard.origen_empresa_id = companies[:1] if len(companies) == 1 else False
            keys = self._origin_keys(equipments)
            is_dept = len(keys) == 1 and next(iter(keys), (False, False))[0] == 'department'
            wizard.es_origen_departamento = bool(is_dept)
            wizard.origen_department_id = (
                equipments[0].department_id if is_dept else False
            )

    @api.depends('bodega_employee_id', 'bodega_employee_id.department_id')
    def _compute_bodega_department(self):
        for wizard in self:
            wizard.bodega_department_id = wizard.bodega_employee_id.department_id

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

    @api.onchange('bodega_employee_id')
    def _onchange_bodega_employee_id_return(self):
        self.bodega_receptor_id = False

    def _check_return_source(self, equipments):
        keys = self._origin_keys(equipments)
        if len(keys) != 1 or next(iter(keys), ('empty', False))[0] == 'empty':
            raise UserError(_(
                'Para un acta de devolución conjunta, seleccione equipos del '
                'mismo departamento o asignados al mismo empleado. '
                'No mezcle responsables diferentes en una sola acta.'
            ))
        kind, record_id = next(iter(keys))
        employee = self.empleado_actual_id
        if not employee or not employee.exists():
            raise UserError(_('Seleccione el empleado actual que realiza la devolución.'))
        if kind == 'department':
            department = self.env['hr.department'].browse(record_id)
            if employee.department_id != department:
                raise UserError(_(
                    'El empleado que devuelve los equipos debe pertenecer al '
                    'departamento "%s".'
                ) % department.display_name)
        elif employee.id != record_id:
            raise UserError(_(
                'El empleado actual debe ser el empleado al que están asignados los equipos.'
            ))
        company_ids = {(eq.company_id or self.env.company).id for eq in equipments}
        if len(company_ids) != 1:
            raise UserError(_('Los equipos seleccionados deben pertenecer a una sola empresa.'))
        company_id = next(iter(company_ids))
        if employee.company_id and employee.company_id.id != company_id:
            raise UserError(_('El empleado que realiza la devolución pertenece a otra empresa.'))
        if employee.es_bodega:
            raise UserError(_(
                'El empleado actual ya está marcado como bodega. '
                'Seleccione equipos pendientes de devolución, no equipos ya devueltos.'
            ))
        return company_id

    def action_generate_report(self):
        self.ensure_one()
        if self.report_type != 'return':
            # La entrega y la entrega de uniformes siguen el comportamiento
            # de maintenance_report y maintenance_report_unifor.
            if self.report_type == 'delivery' and self.equipment_ids:
                dept_equipments = self.equipment_ids.filtered(
                    lambda eq: eq.equipment_assign_to == 'department' and eq.department_id
                )
                if dept_equipments:
                    department_ids = self.equipment_ids.mapped('department_id').ids
                    if len(dept_equipments) != len(self.equipment_ids) or len(set(department_ids)) != 1:
                        raise UserError(_(
                            'Para imprimir el listado de firmas de un departamento, '
                            'seleccione solamente equipos asignados a ese mismo departamento.'
                        ))
                    if not dept_equipments[0]._get_department_delivery_signers():
                        raise UserError(_(
                            'El departamento "%s" no tiene empleados activos para firmar.'
                        ) % dept_equipments[0].department_id.display_name)
            return super().action_generate_report()

        equipments = self.equipment_ids.exists()
        if not equipments:
            raise UserError(_('Debe seleccionar al menos un equipo.'))
        company_id = self._check_return_source(equipments)
        if not self.entregado_por_id:
            raise UserError(_('Seleccione el encargado de entrega/recepción de equipos.'))
        if not self.bodega_employee_id or not self.bodega_receptor_id:
            raise UserError(_(
                'Seleccione la Bodega de devolución y el empleado que recibió los equipos.'
            ))

        # Reutilizar EXACTAMENTE el registro y la validación existente: no se
        # duplican las reglas de bodega, receptor, historial ni chatter.
        assignment = self.env['maintenance.equipment.bodega.wizard'].create({
            'equipment_ids': [(6, 0, equipments.ids)],
            'company_id': company_id,
            'bodega_employee_id': self.bodega_employee_id.id,
            'bodega_receptor_id': self.bodega_receptor_id.id,
        })
        assignment._apply_assignment(return_employee=self.empleado_actual_id)
        equipments.write({'entregado_por_id': self.entregado_por_id.id})
        return self.env.ref(
            'maintenance_report.maintenance_equipment_return_report'
        ).report_action(equipments)
