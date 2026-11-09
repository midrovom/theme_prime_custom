# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import ValidationError


class LoyaltyProgram(models.Model):
    _inherit = 'loyalty.program'

    catastro_warehouse_ids = fields.Many2many(
        comodel_name='stock.warehouse',
        relation='catastro_loyalty_program_warehouse_rel',
        column1='program_id',
        column2='warehouse_id',
        string='Bodegas donde aplica (Ventas / PWA)',
        help=(
            'Seleccione una o varias bodegas donde esta promoción será válida en '
            'cotizaciones de Ventas y Catastro PWA. Si no selecciona ninguna, '
            'se mantiene disponible en todas las bodegas, como hasta ahora. '
            'No controla promociones de Punto de Venta (POS).'
        ),
    )

    @api.constrains('catastro_warehouse_ids', 'company_id')
    def _check_catastro_warehouses_company(self):
        for program in self:
            if not program.company_id:
                continue
            # Odoo 18 also permits a parent-company Loyalty program for
            # orders in its direct child companies. Follow that same scope.
            if any(
                warehouse.company_id != program.company_id
                and warehouse.company_id.parent_id != program.company_id
                for warehouse in program.catastro_warehouse_ids
            ):
                raise ValidationError(
                    'Las bodegas de la promoción deben pertenecer a la empresa '
                    'del programa Loyalty.'
                )
