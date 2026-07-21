from odoo import models
import logging

_logger = logging.getLogger(__name__)

class ProductTemplateInherit(models.Model):
    _inherit = "product.template"

    def update_ribbon_status(self):
        products = self.search([])  # todos los productos
        for product in products:
            if product.qty_available <= 0:
                product.write({
                    'allow_out_of_stock_order': False,
                    'website_ribbon_id': self.env.ref('website_sale_stock.ribbon_out_of_stock').id
                })
                _logger.info(f"Producto {product.default_code} marcado como AGOTADO")
            else:
                product.write({
                    'allow_out_of_stock_order': True,
                    'website_ribbon_id': False
                })
                _logger.info(f"Producto {product.default_code} marcado como DISPONIBLE")
