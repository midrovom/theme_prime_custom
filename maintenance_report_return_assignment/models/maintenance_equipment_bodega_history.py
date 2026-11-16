# -*- coding: utf-8 -*-
from odoo import fields, models


class MaintenanceEquipmentBodegaHistory(models.Model):
    """Registro de entregas y devoluciones de equipos.

    Además de las relaciones Many2one se guardan nombres al momento del
    movimiento, para que cambios futuros de nombre no reescriban la historia.
    """

    _name = 'maintenance.equipment.bodega.history'
    _description = 'Historial de movimientos de equipos'
    _order = 'movement_date desc, id desc'
    _rec_name = 'equipment_id'

    equipment_id = fields.Many2one(
        'maintenance.equipment', string='Equipo', required=True,
        index=True, readonly=True, ondelete='cascade',
    )
    company_id = fields.Many2one(
        'res.company', string='Empresa', required=True,
        index=True, readonly=True,
    )
    movement_date = fields.Datetime(
        string='Fecha del movimiento', required=True, readonly=True,
        default=fields.Datetime.now,
    )
    previous_employee_id = fields.Many2one(
        'hr.employee', string='Empleado anterior', readonly=True,
        ondelete='set null',
    )
    previous_department_id = fields.Many2one(
        'hr.department', string='Departamento anterior', readonly=True,
        ondelete='set null',
    )
    movement_type = fields.Selection(
        [('employee_to_warehouse', 'Devolución de empleado a bodega'),
         ('department_return', 'Devolución de departamento sin cambio de asignación'),
         ('employee_delivery', 'Entrega a empleado'),
         ('department_delivery', 'Entrega a departamento')],
        string='Tipo de movimiento', default='employee_to_warehouse',
        required=True, readonly=True, index=True,
    )
    warehouse_employee_id = fields.Many2one(
        'hr.employee', string='Bodega de devolución',
        readonly=True, ondelete='restrict',
    )
    destination_department_id = fields.Many2one(
        'hr.department', string='Departamento receptor', readonly=True,
        ondelete='set null',
    )
    receiver_employee_id = fields.Many2one(
        'hr.employee', string='Recibido por (empleado)', readonly=True,
        ondelete='set null',
    )
    previous_receiver_employee_id = fields.Many2one(
        'hr.employee', string='Receptor anterior', readonly=True,
        ondelete='set null',
    )
    registered_by_id = fields.Many2one(
        'res.users', string='Registrado por', readonly=True,
        ondelete='set null',
    )

    # Nombres históricos: se conservan incluso si cambia el nombre del
    # empleado o se desactiva un usuario posteriormente.
    previous_employee_name = fields.Char(
        string='Empleado anterior', readonly=True,
    )
    previous_department_name = fields.Char(
        string='Departamento de origen', readonly=True,
    )
    warehouse_name = fields.Char(
        string='Bodega', readonly=True,
    )
    receiver_name = fields.Char(
        string='Recibido por', readonly=True,
    )
    previous_receiver_name = fields.Char(
        string='Receptor anterior', readonly=True,
    )
    registered_by_name = fields.Char(
        string='Usuario que registró', readonly=True,
    )

    # Entregas: datos propios, sin reutilizar campos de devoluciones.
    # El identificador del wizard evita duplicar la entrega al volver a pulsar
    # Generar PDF desde la MISMA ventana. Otra acta es un evento nuevo.
    delivery_wizard_token = fields.Char(
        string='Identificador del acta de entrega', readonly=True, copy=False,
        index=True,
    )
    delivery_sender_employee_id = fields.Many2one(
        'hr.employee', string='Entregado por (empleado)', readonly=True,
        ondelete='set null',
    )
    delivery_target_employee_id = fields.Many2one(
        'hr.employee', string='Empleado destinatario', readonly=True,
        ondelete='set null',
    )
    delivery_target_department_id = fields.Many2one(
        'hr.department', string='Departamento destinatario', readonly=True,
        ondelete='set null',
    )
    delivery_sender_name = fields.Char(
        string='Entregado por', readonly=True,
    )
    delivery_target_name = fields.Char(
        string='Entrega a', readonly=True,
    )
    delivery_department_signers = fields.Text(
        string='Empleados del departamento al generar el acta', readonly=True,
        help='Fotografía de los empleados incluidos en el acta, ' 
             'para mantener la trazabilidad si después cambia el personal.',
    )

    _sql_constraints = [
        (
            'equipment_delivery_wizard_unique',
            'unique(equipment_id, delivery_wizard_token)',
            'La entrega de este equipo ya está registrada para esta acta.',
        ),
    ]
