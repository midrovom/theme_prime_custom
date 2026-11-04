# -*- coding: utf-8 -*-
from odoo import _, fields, models
from odoo.exceptions import UserError


class MaintenanceReportWizard(models.TransientModel):
    _inherit = 'maintenance.report.wizard'

    # Exactly the same relation as maintenance.equipment.employee_id.
    # No contacts, checkboxes, warehouse-to-employee mapping or new employees.
    employee_id = fields.Many2one(
        'hr.employee',
        string='Bodega de devolución',
        help=(
            'Seleccione directamente el empleado que recibirá los equipos '
            '(por ejemplo, Bodega Sistema). Al generar el acta, el campo '
            'Empleado de cada equipo cambiará al seleccionado.'
        ),
    )

    def action_generate_report(self):
        self.ensure_one()
        if self.report_type != 'return':
            # Delivery and uniform reports keep their existing behavior.
            return super().action_generate_report()

        nuevo_empleado = self.employee_id
        if not nuevo_empleado:
            raise UserError(_('Seleccione una Bodega de devolución (Empleado).'))

        equipments = self.equipment_ids
        if not equipments:
            raise UserError(_('Debe seleccionar al menos un equipo.'))

        # The original return PDF uses docs[0].employee_id in the intro and
        # signature. All items in the acta therefore must come from one person.
        if any(not equipment.employee_id for equipment in equipments):
            raise UserError(_(
                'Todos los equipos deben tener un empleado asignado antes '
                'de generar el acta de devolución.'
            ))
        empleados_anteriores = equipments.mapped('employee_id')
        if len(empleados_anteriores) != 1:
            raise UserError(_(
                'Seleccione equipos de un mismo empleado para cada acta '
                'de devolución.'
            ))

        if len(equipments.mapped('company_id')) > 1:
            raise UserError(_(
                'No se pueden incluir equipos de distintas empresas '
                'en una misma acta de devolución.'
            ))
        empleado_anterior = empleados_anteriores
        if empleado_anterior == nuevo_empleado:
            raise UserError(_(
                'El equipo ya está asignado a "%s". '
                'Seleccione otro empleado de destino.'
            ) % nuevo_empleado.display_name)

        # Call the existing report flow, which updates entregado_por_id and
        # prepares the report action. Odoo renders the PDF afterward.
        action = super().action_generate_report()
        equipments.write({
            'empleado_devolucion_anterior_id': empleado_anterior.id,
            'employee_id': nuevo_empleado.id,
        })
        return action
