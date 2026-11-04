# -*- coding: utf-8 -*-
from collections import Counter

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class SaleOrderSelectProducts(models.TransientModel):
    _name = 'sale.order.select.products'
    _description = 'Seleccionar Productos para Orden de Venta'

    order_id = fields.Many2one('sale.order', string='Cotización', required=True)
    product_ids = fields.Many2many('product.product', string='Productos a agregar')
    warehouse_id = fields.Many2one('stock.warehouse', string='Bodega', required=True)
    available_product_ids = fields.Many2many(
        'product.product', compute='_compute_available_product_ids',
        string='Productos disponibles',
    )

    @api.depends('warehouse_id')
    def _compute_available_product_ids(self):
        Quant = self.env['stock.quant']
        for record in self:
            if not record.warehouse_id:
                record.available_product_ids = False
                continue
            groups = Quant.read_group([
                ('location_id', '=', record.warehouse_id.lot_stock_id.id),
                ('quantity', '>', 0),
            ], ['product_id'], ['product_id'], lazy=False)
            ids = [row['product_id'][0] for row in groups if row.get('product_id')]
            record.available_product_ids = [(6, 0, ids)]

    @api.onchange('warehouse_id')
    def _onchange_warehouse_id(self):
        if self.product_ids:
            self.product_ids = False
            return {'warning': {
                'title': _('Cambio de bodega'),
                'message': _('La selección anterior se limpió para consultar el stock de la nueva bodega.'),
            }}

    @api.onchange('product_ids')
    def _onchange_validate_location(self):
        if self.product_ids and not self.warehouse_id:
            self.product_ids = False
            return {'warning': {
                'title': _('Bodega requerida'),
                'message': _('Seleccione una bodega antes de agregar productos.'),
            }}

    def add_products_to_order(self):
        self.ensure_one()
        order = self.order_id.exists()
        if not order:
            raise UserError(_('No se encontró la cotización. Guarde la cotización antes de usar este asistente.'))
        if order.export_send == 'E':
            raise ValidationError(_('La cotización %s ya se envió a Radis.') % order.name)
        if not self.warehouse_id:
            raise ValidationError(_('Debe seleccionar una bodega.'))
        if self.warehouse_id.company_id != order.company_id:
            raise ValidationError(_('La bodega debe corresponder a la compañía de la cotización.'))
        if not self.env.user.has_group('stock_api_assing.group_multi_warehouse') and self.warehouse_id != order.warehouse_id:
            raise ValidationError(_('No tiene permisos para usar una bodega distinta de la cotización.'))
        existing = {(line.product_id.id, line.warehouse_id.id)
                    for line in order.order_line if line.product_id and not line.display_type}
        for product in self.product_ids:
            key = (product.id, self.warehouse_id.id)
            if key in existing:
                raise ValidationError(_(
                    'Producto duplicado: %s (Bodega: %s)'
                ) % (product.display_name, self.warehouse_id.display_name))
            if product not in self.available_product_ids:
                raise ValidationError(_('El producto %s no tiene stock positivo en la bodega seleccionada.') % product.display_name)
            existing.add(key)
        self.env['sale.order.line'].create([{
            'order_id': order.id,
            'product_id': product.id,
            'name': product.display_name,
            'product_uom_qty': 1,
            'price_unit': product.lst_price,
            'warehouse_id': self.warehouse_id.id,
        } for product in self.product_ids])
        return {'type': 'ir.actions.act_window_close'}
