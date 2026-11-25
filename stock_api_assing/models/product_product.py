from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    peso = fields.Float('Peso')

class ProductProduct(models.Model):
    _inherit = 'product.product'

    peso = fields.Float(related='product_tmpl_id.peso')
    
    location_qty = fields.Char(
        string='Stock en Bodega',
        compute="_compute_location_qty",
        help='Stock disponible en una bodega específica',
    )

    def _compute_location_qty(self):
        warehouse_id = self.env.context.get('warehouse_id')

        _logger.info(f"MOSTRANDO CONTEXT >>>>> { warehouse_id }")

        stock_warehouse = self.env["stock.warehouse"].search([("id", "=", warehouse_id)])
        location_id = stock_warehouse.lot_stock_id.id
        for product in self:
            if not location_id:
                product.location_qty = "⚠ Seleccione ubicación"
            else:
                quants = self.env['stock.quant'].search([
                    ('product_id', '=', product.id),
                    ('location_id', '=', location_id)
                ])
                qty = sum(quants.mapped('quantity'))
                product.location_qty = str(qty)


            

    # @api.depends('stock_quant_ids')
    # def _compute_warehouse_qty(self):
    #     warehouse = self.env.user.property_warehouse_id
    #     for product in self:
    #         quants = self.env['stock.quant'].search([
    #             ('product_id', '=', product.id),
    #             ('location_id', 'child_of', warehouse.lot_stock_id.id),
    #         ])
    #         product.warehouse_qty = sum(quants.mapped('quantity'))
    