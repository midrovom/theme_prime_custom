from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

import logging

_logger = logging.getLogger(__name__)

class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    stock_quantity = fields.Float(string="Stock", compute="_compute_stock_quantity", store=True)

    negotiable_price = fields.Float('Precio negociable')
    negotiable_price_subtotal = fields.Float(
        string="Subtotal negociable",
        compute='_compute_amount_negotiable',
        store=False, precompute=True
    )


    warehouse_id = fields.Many2one(
        'stock.warehouse', string='Bodega', required=True, related=False
    )

    readonly_price_unit = fields.Boolean(
        compute="_compute_readonly_price_unit",
        store=False
    )

    @api.depends()
    def _compute_readonly_price_unit(self):
        group = self.env.ref("stock_api_assing.group_price_unit")
        for line in self:
            line.readonly_price_unit = self.env.user in group.users

    # product_id = fields.Many2one(
    #     comodel_name='product.product',
    #     string="Product",
    #     change_default=True, ondelete='restrict', check_company=True, index='btree_not_null',
    #     domain=lambda self: self._get_product_domain()
    # )


    #####

    @api.onchange('warehouse_id')
    def _onchange_location_id(self):
        domain = []
        if self.warehouse_id:
            location_id = self.warehouse_id.lot_stock_id
            quants = self.env['stock.quant'].read_group(
                [('location_id', '=', location_id.id), ('quantity', '>', 0)],
                ['product_id'],
                ['product_id']
            )
            product_ids = [q['product_id'][0] for q in quants if q['product_id']]
            domain = [('id', 'in', product_ids)]

        return {'domain': {'product_id': domain}}
    

    @api.onchange('product_id')
    def _onchange_validate_location(self):
        for record in self:
            if record.product_id:
                if record.order_id and not record.order_id.warehouse_id:
                    record.product_id = False
                    return {
                        'warning': {
                            'title': _('Ubicación requerida'),
                            'message': _(
                                'Por favor, seleccione la ubicación antes de agregar productos, '
                                'para visualizar correctamente el stock disponible en la bodega.'
                            )
                        }
                    }
                
    #####
    
    # def _get_product_domain(self):
    #     warehouse_id = self.env.user.property_warehouse_id
        
    #     # Obtener todos los productos con stock en esta bodega
    #     quant_ids = self.env['stock.quant'].search([
    #         ('quantity', '>', 0),
    #         ('location_id', '=', warehouse_id.lot_stock_id.id)
    #     ])
    #     product_ids = quant_ids.mapped('product_id').ids
        
    #     return [('id', 'in', product_ids)]


    @api.depends('product_uom_qty', 'discount', 'negotiable_price', 'tax_id')
    # def _compute_amount_negotiable(self):
    #     for line in self:
    #         tax_results = self.env['account.tax'].with_company(line.company_id)._compute_taxes(
    #             [line._convert_to_tax_base_line_dict_negotiable()]
    #         )
    #         totals = list(tax_results['totals'].values())[0]
    #         amount_untaxed = totals['amount_untaxed']

    #         # Solo calculamos y asignamos nuestro nuevo campo
    #         line.negotiable_price_subtotal = amount_untaxed

    # def _convert_to_tax_base_line_dict_negotiable(self):
    #     self.ensure_one()

    #     price_unit = self.negotiable_price

    #     if self.tax_id:
    #         tax = self.tax_id[0].amount / 100
    #         price_unit = self.negotiable_price / (1 + tax)

    #     return self.env['account.tax']._convert_to_tax_base_line_dict(
    #         self,
    #         partner=self.order_id.partner_id,
    #         currency=self.order_id.currency_id,
    #         product=self.product_id,
    #         taxes=self.tax_id,
    #         price_unit=price_unit,
    #         quantity=self.product_uom_qty,
    #         discount=self.discount,
    #         price_subtotal=None,  # no lo necesitas aquí
    #     )


    def _compute_amount_negotiable(self):
        for line in self:
            base_line = line._prepare_base_line_for_taxes_computation_negotiable()
            self.env['account.tax']._add_tax_details_in_base_line(base_line, line.company_id)
            line.negotiable_price_subtotal = base_line['tax_details']['raw_total_excluded_currency']

    def _prepare_base_line_for_taxes_computation_negotiable(self):
        self.ensure_one()
        price_unit = self.negotiable_price

        if self.tax_id:
            tax = self.tax_id[0].amount / 100
            price_unit = self.negotiable_price / (1 + tax)

        return {
            'record': self,
            'base_amount': price_unit * self.product_uom_qty,
            'base_amount_currency': price_unit * self.product_uom_qty,
            'quantity': self.product_uom_qty,
            'price_unit': price_unit,
            'discount': self.discount,
            'taxes': self.tax_id,
            'currency': self.order_id.currency_id,
            'company': self.order_id.company_id,
            'partner': self.order_id.partner_id,
        }

    # @api.depends('product_id')
    # def _compute_stock_quantity(self):
    #     warehouse_id = self.warehouse_id
    #     location_id = warehouse_id.lot_stock_id
    #     for line in self:
    #         if line.product_id:
    #             stock_quant = self.env['stock.quant'].search([
    #                 ('product_id', '=', line.product_id.id),
    #                 # ('location_id.usage', '=', 'internal')
    #                 ('location_id', '=', location_id.id)
    #             ], limit=1)
    #             line.stock_quantity = stock_quant.quantity if stock_quant else 0


    @api.depends('product_id', 'warehouse_id')
    def _compute_stock_quantity(self):
        for line in self:
            line.stock_quantity = 0  # default
            
            if not line.product_id or not line.warehouse_id:
                continue

            warehouse_id = line.warehouse_id
            location_id = warehouse_id.lot_stock_id  # aquí sí es singleton

            stock_quant = self.env['stock.quant'].search([
                ('product_id', '=', line.product_id.id),
                ('location_id', '=', location_id.id)
            ], limit=1)

            line.stock_quantity = stock_quant.quantity if stock_quant else 0

    @api.constrains('product_uom_qty')
    def _check_product_stock(self):
        # company = self.env.user.company_id
        for line in self:
            # if company.company_registry:
            #     continue

            if line.product_id.type != 'consu':
                continue  # No aplica para servicios ni consumibles

            # Obtener el stock disponible en la ubicación del almacén del pedido
            location_id = line.warehouse_id.lot_stock_id
            stock_quant = self.env['stock.quant'].search([
                ('product_id', '=', line.product_id.id),
                ('location_id', '=', location_id.id)
            ], limit=1)
            available_qty = stock_quant.quantity if stock_quant else 0

            if line.product_uom_qty > available_qty:
                raise ValidationError(
                    f"La cantidad solicitada: { line.product_uom_qty } excede el stock disponible: { available_qty } que hay en la bodega { line.warehouse_id.name } del producto '{ line.product_id.name }'."
                )
            

    @api.model
    # def create(self, vals):
    #     order = self.env['sale.order'].browse(vals.get('order_id'))
    #     if order.export_send == 'E' and self.env.context.get('bypass_radis_lock') != True:
    #         raise ValidationError(f"No se pueden agregar líneas a la Orden {order.name} porque ya fue enviada a Radis.")
    #     return super(SaleOrderLine, self).create(vals)

    def create(self, vals):
        order = self.env['sale.order'].browse(vals.get('order_id'))
        if order and order.warehouse_id and not vals.get('warehouse_id'):
            vals['warehouse_id'] = order.warehouse_id.id
        if order.export_send == 'E' and self.env.context.get('bypass_radis_lock') != True:
            raise ValidationError(f"No se pueden agregar líneas a la Orden {order.name} porque ya fue enviada a Radis.")
        return super(SaleOrderLine, self).create(vals)

    def write(self, vals):
        for line in self:
            if line.order_id.export_send == 'E' and self.env.context.get('bypass_radis_lock') != True:
                raise ValidationError(f"No se pueden modificar líneas de la Orden {line.order_id.name} porque ya fue enviada a Radis.")
        return super(SaleOrderLine, self).write(vals)
    
    def unlink(self):
        for line in self:
            if line.order_id.export_send == 'E' and self.env.context.get('bypass_radis_lock') != True:
                raise ValidationError(f"No se pueden eliminar líneas de la Orden {line.order_id.name} porque ya fue enviada a Radis.")
        return super(SaleOrderLine, self).unlink()
