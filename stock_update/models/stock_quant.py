from odoo import models

class StockQuant(models.Model):
    _inherit = 'stock.quant'

    def write(self, vals):
        res = super().write(vals)
        # Usamos el ID directo (2) o búsqueda por nombre
        agotado_ribbon = self.env['product.ribbon'].browse(2)

        for quant in self:
            product = quant.product_id.product_tmpl_id
            if quant.inventory_quantity_auto_apply <= 0:
                product.allow_out_of_stock_order = False
                if agotado_ribbon:
                    product.website_ribbon_id = agotado_ribbon.id
            else:
                product.allow_out_of_stock_order = True
                product.website_ribbon_id = False
        return res
