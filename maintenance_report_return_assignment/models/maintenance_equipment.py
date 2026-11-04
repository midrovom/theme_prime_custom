# -*- coding: utf-8 -*-
from odoo import fields, models


class MaintenanceEquipment(models.Model):
    _inherit = 'maintenance.equipment'

    empleado_devolucion_anterior_id = fields.Many2one(
        'hr.employee',
        string='Empleado que devolvio el equipo',
        copy=False,
        readonly=True,
        tracking=True,
        help=(
            'Empleado asignado antes de la ultima devolucion. '
            'Se mantiene para que el acta de devolucion identifique '
            'correctamente a quien entrego el equipo.'
        ),
    )

    bodega_devolucion_id = fields.Many2one(
        'res.partner',
        string='Bodega de devolución',
        domain=[('es_bodega', '=', True)],
        copy=False,
        readonly=True,
        tracking=True,
        ondelete='restrict',
        help=(
            'Contacto receptor del equipo en la ultima acta de devolucion. '
            'No modifica el proveedor del equipo.'
        ),
    )
