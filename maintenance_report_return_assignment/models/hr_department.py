# -*- coding: utf-8 -*-
from odoo import fields, models


class HrDepartment(models.Model):
    _inherit = 'hr.department'

    permite_recepcion_equipos = fields.Boolean(
        string='Habilitar como departamento receptor',
        default=False,
        help='Si está marcado, el departamento aparecerá en Departamento receptor '
             'del acta de devolución de equipos asignados por departamento. '
             'No altera la asignación del equipo.',
    )
