from odoo import models, api

class StockQuant(models.Model):
    _inherit = 'stock.quant'

    def write(self, vals):
        res = super().write(vals)
        agotado_ribbon = self.env.ref('stock_update.ribbon_out_of_stock', raise_if_not_found=False)

        for quant in self:
            product = quant.product_id.product_tmpl_id
            if quant.inventory_quantity_auto_apply <= 0:
                # Stock agotado
                product.allow_out_of_stock_order = False
                if agotado_ribbon:
                    product.website_ribbon_id = agotado_ribbon.id
            else:
                # Stock disponible nuevamente
                product.allow_out_of_stock_order = True
                product.website_ribbon_id = False  # opcional: limpiar la etiqueta
        return res
