from odoo import models
import logging

_logger = logging.getLogger(__name__)

class ProductInherit(models.Model):
    _inherit = "product.product"

    def action_update_quantity_on_hand(self):
        # Mantener la lógica original
        advanced_option_groups = [
            'stock.group_stock_multi_locations',
            'stock.group_tracking_owner',
            'stock.group_tracking_lot'
        ]
        if any(self.env.user.has_group(g) for g in advanced_option_groups) or self.tracking != 'none':
            return self.action_open_quants()
        else:
            default_product_id = self.env.context.get(
                'default_product_id',
                len(self.product_variant_ids) == 1 and self.product_variant_id.id
            )
            action = self.env["ir.actions.actions"]._for_xml_id("stock.action_change_product_quantity")
            action['context'] = dict(
                self.env.context,
                default_product_id=default_product_id,
                default_product_tmpl_id=self.id
            )

            # Nueva lógica: marcar agotado o disponible en la plantilla
            available_qty = self.qty_available
            if available_qty <= 0:
                self.product_tmpl_id.write({
                    'allow_out_of_stock_order': False,
                    'website_ribbon_id': self.env.ref('website_sale_stock.ribbon_out_of_stock').id
                })
                _logger.info(f"Producto {self.default_code} marcado como AGOTADO")
            else:
                self.product_tmpl_id.write({
                    'allow_out_of_stock_order': True,
                    'website_ribbon_id': False  # Quitar ribbon de agotado
                })
                _logger.info(f"Producto {self.default_code} marcado como DISPONIBLE")

            return action
