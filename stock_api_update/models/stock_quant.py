import logging
import requests
from datetime import datetime
from odoo import models, api, fields

_logger = logging.getLogger(__name__)

class StockAPISyncInherit(models.Model):
    _inherit = 'stock.api.sync'   

    def _update_stock(self, product, stock, warehouse):
        # Obtener la ubicación de stock de la bodega
        stock_location = warehouse.lot_stock_id
        if not stock_location:
            _logger.warning(f"La bodega {warehouse.name} no tiene una ubicación de stock configurada.")
            return

        # Verificar que el producto tenga una variante
        product_variant = product.product_variant_id
        if not product_variant:
            _logger.warning(f"El producto {product.default_code} no tiene una variante asociada.")
            return

        # Buscar el registro de stock.quant
        quant = self.env['stock.quant'].search([
            ('product_id', '=', product_variant.id),
            ('location_id', '=', stock_location.id),
        ], limit=1)

        if quant:
            # Actualizar el stock existente
            quant.sudo().write({'quantity': stock, 'check_update': True})
        else:
            # Crear un nuevo registro de stock
            self.env['stock.quant'].sudo().create({
                'product_id': product_variant.id,
                'location_id': stock_location.id,
                'quantity': stock,
                'check_update': True,
            })

        _logger.info(f"Stock actualizado para el producto {product.default_code} en la bodega {warehouse.name}: {stock}")

        # Nueva lógica: marcar agotado o disponible
        if stock <= 0:
            product.write({
                'allow_out_of_stock_order': False,
                'website_ribbon_id': self.env.ref('website_sale_stock.ribbon_out_of_stock').id
            })
            _logger.info(f"Producto {product.default_code} marcado como AGOTADO")
        else:
            product.write({
                'allow_out_of_stock_order': True,
                'website_ribbon_id': False  # Quitar ribbon de agotado
            })
            _logger.info(f"Producto {product.default_code} marcado como DISPONIBLE")

