# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from odoo.tools import float_compare


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    stock_quantity = fields.Float(string='Stock', compute='_compute_stock_quantity')
    negotiable_price = fields.Float('Precio negociable')
    negotiable_price_subtotal = fields.Float(
        string='Subtotal negociable', compute='_compute_amount_negotiable', store=False,
    )
    warehouse_id = fields.Many2one('stock.warehouse', string='Bodega', check_company=True)
    readonly_price_unit = fields.Boolean(compute='_compute_readonly_price_unit')

    def _compute_readonly_price_unit(self):
        readonly = self.env.user.has_group('stock_api_assing.group_price_unit')
        for line in self:
            line.readonly_price_unit = readonly

    def _get_negotiable_price_excluded(self):
        """Conserva contrato Radis: precio negociable con impuesto simple incluido."""
        self.ensure_one()
        tax = self.tax_id[:1]
        return self.negotiable_price / (1.0 + tax.amount / 100) if tax and (1.0 + tax.amount / 100) else self.negotiable_price

    def _convert_to_tax_base_line_dict_negotiable(self):
        self.ensure_one()
        return self._prepare_base_line_for_taxes_computation(
            price_unit=self._get_negotiable_price_excluded(),
            quantity=self.product_uom_qty, discount=self.discount,
        )

    @api.depends('product_uom_qty', 'discount', 'negotiable_price', 'tax_id', 'company_id')
    def _compute_amount_negotiable(self):
        AccountTax = self.env['account.tax']
        for line in self:
            base_line = line._convert_to_tax_base_line_dict_negotiable()
            AccountTax._add_tax_details_in_base_line(base_line, line.company_id)
            line.negotiable_price_subtotal = base_line['tax_details']['raw_total_excluded_currency']

    @api.depends('product_id', 'warehouse_id')
    def _compute_stock_quantity(self):
        Quant = self.env['stock.quant']
        for line in self:
            if not line.product_id or not line.warehouse_id:
                line.stock_quantity = 0.0
                continue
            quants = Quant.search([
                ('product_id', '=', line.product_id.id),
                ('location_id', '=', line.warehouse_id.lot_stock_id.id),
            ])
            line.stock_quantity = sum(quants.mapped('quantity'))

    @api.constrains('product_uom_qty', 'product_id', 'warehouse_id')
    def _check_product_stock(self):
        Quant = self.env['stock.quant']
        for line in self:
            if line.display_type or not line.product_id or not line.product_id.is_storable:
                continue
            warehouse = line.warehouse_id or line.order_id.warehouse_id
            if not warehouse:
                continue
            quants = Quant.search([
                ('product_id', '=', line.product_id.id),
                ('location_id', '=', warehouse.lot_stock_id.id),
            ])
            available_qty = sum(quants.mapped('quantity'))
            if float_compare(line.product_uom_qty, available_qty,
                             precision_rounding=line.product_uom.rounding or line.product_id.uom_id.rounding) > 0:
                raise ValidationError(_(
                    'La cantidad solicitada: %(qty)s excede el stock disponible: %(available)s '
                    'en la bodega %(warehouse)s para el producto %(product)s.'
                ) % {
                    'qty': line.product_uom_qty, 'available': available_qty,
                    'warehouse': warehouse.name, 'product': line.product_id.display_name,
                })

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            order = self.env['sale.order'].browse(vals.get('order_id')).exists() if vals.get('order_id') else self.env['sale.order']
            if order and order.export_send == 'E' and not self.env.context.get('bypass_radis_lock'):
                raise ValidationError(_('No se pueden agregar líneas a la Orden %s: enviada a Radis.') % order.name)
            if order and not vals.get('warehouse_id') and vals.get('product_id'):
                vals['warehouse_id'] = order.warehouse_id.id
        return super().create(vals_list)

    def write(self, vals):
        if not self.env.context.get('bypass_radis_lock'):
            for line in self:
                if line.order_id.export_send == 'E':
                    raise ValidationError(_('No se pueden modificar líneas de la Orden %s: enviada a Radis.') % line.order_id.name)
        return super().write(vals)

    def unlink(self):
        if not self.env.context.get('bypass_radis_lock'):
            for line in self:
                if line.order_id.export_send == 'E':
                    raise ValidationError(_('No se pueden eliminar líneas de la Orden %s: enviada a Radis.') % line.order_id.name)
        return super().unlink()
