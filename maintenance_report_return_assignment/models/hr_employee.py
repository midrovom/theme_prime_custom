# -*- coding: utf-8 -*-
from odoo import fields, models


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    es_bodega = fields.Boolean(
        string='Es bodega',
        default=False,
        help='Marcar para que este empleado pueda recibir equipos mediante el botón Asignar a bodega.',
    )
