# -*- coding: utf-8 -*-
from odoo import _, fields, models
from odoo.exceptions import UserError


class MaintenanceEquipment(models.Model):
    _inherit = 'maintenance.equipment'

    # Campos existentes: no cambiar nombres ni tipos para conservar los datos.
    empleado_devolucion_anterior_id = fields.Many2one(
        'hr.employee', string='Empleado anterior', readonly=True, copy=False,
        tracking=True,
        help='Empleado del equipo antes de su última transferencia a bodega.',
    )
    bodega_asignado_por_id = fields.Many2one(
        'res.users', string='Registrado por', readonly=True, copy=False,
        tracking=True,
        help='Usuario de Odoo que efectuó el último movimiento a bodega.',
    )
    bodega_asignacion_fecha = fields.Datetime(
        string='Fecha de asignación a bodega', readonly=True, copy=False,
        tracking=True,
    )

    # Último movimiento: el equipo queda a nombre de la BODEGA (employee_id),
    # pero se identifica por separado a quien lo recibió físicamente.
    bodega_destino_ultima_id = fields.Many2one(
        'hr.employee', string='Bodega de devolución', readonly=True,
        copy=False, tracking=True,
    )
    bodega_receptor_ultimo_id = fields.Many2one(
        'hr.employee', string='Recibido por (empleado)', readonly=True,
        copy=False, tracking=True,
    )
    # Último documento generado: fotografía del firmante y receptor. En
    # devoluciones departamentales employee_id y department_id NO se alteran.
    devolucion_acta_empleado_id = fields.Many2one(
        'hr.employee', string='Último empleado que devolvió',
        readonly=True, copy=False, ondelete='set null',
    )
    devolucion_acta_departamento_id = fields.Many2one(
        'hr.department', string='Departamento en última devolución',
        readonly=True, copy=False, ondelete='set null',
    )
    devolucion_acta_receptor_id = fields.Many2one(
        'hr.employee', string='Último empleado receptor',
        readonly=True, copy=False, ondelete='set null',
    )
    bodega_historial_ids = fields.One2many(
        'maintenance.equipment.bodega.history', 'equipment_id',
        string='Historial de movimientos y devoluciones', readonly=True,
        copy=False,
    )

    def _get_department_delivery_signers(self):
        """Firmantes del departamento y sus subdepartamentos, sin recortes.

        Se consultan en el momento de imprimir el PDF, para recoger todos
        los empleados incluso si el departamento tiene equipos anidados en
        subdepartamentos. No restringir por empresa del empleado: en varias
        instalaciones el dato es compartido o difiere del equipo.

        Incluir archivados mantiene la capacidad de reimprimir actas
        históricas. En el documento se imprime una fila completa por firmante.
        """
        self.ensure_one()
        if self.equipment_assign_to != 'department' or not self.department_id:
            return self.env['hr.employee'].browse()
        departments = self.env['hr.department'].sudo().with_context(
            active_test=False
        ).search([('id', 'child_of', self.department_id.id)])
        return self.env['hr.employee'].sudo().with_context(active_test=False).search([
            ('department_id', 'in', departments.ids),
        ], order='name, id')

    def action_open_bodega_assignment(self):
        """Mismo wizard desde ficha, cabecera de lista y Acción masiva."""
        if not self:
            raise UserError(_('Seleccione al menos un equipo para asignar a bodega.'))

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
