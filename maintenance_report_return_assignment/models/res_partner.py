# -*- coding: utf-8 -*-
from odoo import fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    es_bodega = fields.Boolean(
        string='Es bodega',
        default=False,
        help='Permite seleccionar este contacto en el campo Bodega de devolución.',
    )

    bodega_empleado_id = fields.Many2one(
        'hr.employee',
        string='Empleado asociado a bodega',
        ondelete='restrict',
        help=(
            'Empleado de Odoo al que se reasignarán los equipos cuando '
            'se seleccione este contacto como bodega de devolución. '
            'Si está vacío, se buscará un empleado con este contacto laboral '
            'o con el mismo nombre, dentro de la empresa del equipo.'
        ),
    )
