# -*- coding: utf-8 -*-
from odoo import _, fields, models
from odoo.exceptions import UserError


class MaintenanceReportWizard(models.TransientModel):
    _inherit = 'maintenance.report.wizard'

    bodega_devolucion_id = fields.Many2one(
        'res.partner',
        string='Bodega de devolución',
        domain=[('es_bodega', '=', True)],
        help=(
            'Seleccione el contacto que recibirá el equipo devuelto. '
            'Su empleado asociado será el nuevo empleado asignado al equipo.'
        ),
    )

    def _get_empleado_bodega(self, bodega, company):
        """Resolver un hr.employee de la empresa; nunca asociar al azar.

        El wizard selecciona res.partner, pero maintenance.equipment.employee_id
        requiere hr.employee.  Prioridad: vínculo explícito en Contactos,
        contacto laboral del empleado, nombre idéntico no ambiguo.
        """
        self.ensure_one()
        Employee = self.env['hr.employee'].with_company(company)

        if bodega.company_id and bodega.company_id != company:
            raise UserError(_(
                'La Bodega de devolución "%s" pertenece a otra empresa. '
                'Seleccione una bodega de la misma empresa del equipo.'
            ) % bodega.display_name)

        if bodega.bodega_empleado_id:
            empleado = bodega.bodega_empleado_id
            if empleado.company_id != company:
                raise UserError(_(
                    'El empleado "%s" vinculado a la bodega "%s" pertenece '
                    'a otra empresa. Configure un empleado de "%s".'
                ) % (empleado.name, bodega.display_name, company.display_name))
            if not empleado.active:
                raise UserError(_(
                    'El empleado "%s" vinculado a la bodega no está activo.'
                ) % empleado.name)
            return empleado

        # Usar la relación nativa de Odoo 18: hr.employee.work_contact_id.
        vinculados = Employee.search([
            ('work_contact_id', '=', bodega.id),
            ('company_id', '=', company.id),
            ('active', '=', True),
        ], limit=2)
        if len(vinculados) == 1:
            return vinculados
        if len(vinculados) > 1:
            raise UserError(_(
                'La bodega "%s" está vinculada con varios empleados. '
                'En Contactos seleccione el campo "Empleado asociado a bodega".'
            ) % bodega.display_name)

        # Compatible con instalaciones donde Contactos y Empleados se crearon
        # por separado con el mismo nombre (p.ej. "Bodega Sistema").
        coincidencias = Employee.search([
            ('name', '=ilike', bodega.name),
            ('company_id', '=', company.id),
            ('active', '=', True),
        ], limit=2)
        if len(coincidencias) == 1:
            return coincidencias
        if len(coincidencias) > 1:
            raise UserError(_(
                'Existen varios empleados con el nombre "%s". '
                'En Contactos vincule el empleado correcto en '
                '"Empleado asociado a bodega".'
            ) % bodega.name)

        raise UserError(_(
            'No se encontró un empleado para la bodega "%s" en la empresa '
            '"%s". Cree primero el empleado en Empleados y vincúlelo '
            'desde Contactos, en "Empleado asociado a bodega".'
        ) % (bodega.display_name, company.display_name))

    def action_generate_report(self):
        self.ensure_one()
        if self.report_type != 'return':
            # Las entregas normales y uniformes no se ven afectados.
            return super().action_generate_report()

        bodega = self.bodega_devolucion_id
        if not bodega:
            raise UserError(_('Seleccione una Bodega de devolución.'))
        # El dominio del widget se valida otra vez en el servidor.
        if not bodega.es_bodega:
            raise UserError(_(
                'El contacto seleccionado no tiene activada la casilla '
                '"Es bodega". Active esa casilla en Contactos.'
            ))

        equipments = self.equipment_ids
        if not equipments:
            raise UserError(_('Debe seleccionar al menos un equipo.'))

        # Los equipos se devuelven por empleado y por empresa; el PDF
        # original muestra un único empleado en la cabecera y la firma.
        previos = equipments.mapped('employee_id')
        if any(not equipo.employee_id for equipo in equipments):
            raise UserError(_(
                'Todos los equipos del acta deben tener un empleado asignado '
                'antes de realizar la devolución.'
            ))
        if len(previos) != 1:
            raise UserError(_(
                'Seleccione equipos de un mismo empleado para cada acta '
                'de devolución.'
            ))

        companies = equipments.mapped('company_id')
        if len(companies) > 1:
            raise UserError(_(
                'No se pueden mezclar equipos de distintas empresas '
                'en una misma acta de devolución.'
            ))
        company = companies[:1] or self.env.company
        nuevo_empleado = self._get_empleado_bodega(bodega, company)

        # Evitar actas de devolución donde el equipo ya está en esa bodega.
        if previos == nuevo_empleado:
            raise UserError(_(
                'El equipo ya está asignado al empleado de la bodega "%s". '
                'Seleccione equipos que deba devolver otro empleado.'
            ) % bodega.display_name)

        # El método original fija entregado_por_id y devuelve la acción PDF.
        # El PDF se renderiza DESPUÉS; preservar primero al empleado anterior
        # para que el acta identifique al devolvente, no a la bodega.
        action = super().action_generate_report()
        equipments.write({
            'empleado_devolucion_anterior_id': previos.id,
            'bodega_devolucion_id': bodega.id,
            'employee_id': nuevo_empleado.id,
        })
        return action
