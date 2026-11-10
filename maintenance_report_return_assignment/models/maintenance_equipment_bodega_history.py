# -*- coding: utf-8 -*-
from odoo import fields, models


class MaintenanceEquipmentBodegaHistory(models.Model):
    """Registro de los movimientos a bodega, inalterable desde la interfaz.

    Además de las relaciones Many2one se guardan nombres al momento del
    movimiento, para que cambios futuros de nombre no reescriban la historia.
    """

    _name = 'maintenance.equipment.bodega.history'
    _description = 'Historial de asignaciones de equipos a bodega'
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
    warehouse_employee_id = fields.Many2one(
        'hr.employee', string='Bodega de devolución', required=True,
        readonly=True, ondelete='restrict',
    )
    receiver_employee_id = fields.Many2one(
        'hr.employee', string='Recibido por (empleado)', readonly=True,
        ondelete='set null',
    )
    previous_receiver_employee_id = fields.Many2one(
        'hr.employee', string='Receptor anterior en bodega', readonly=True,
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
