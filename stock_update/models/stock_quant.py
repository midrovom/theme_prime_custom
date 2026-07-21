from odoo import models, api

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    @api.depends('qty_available')
    def _compute_stock_flags(self):
        """Si el stock llega a cero:
        - Desactiva el check 'allow_out_of_stock_order'
        - Asigna la etiqueta 'Agotado' en website_ribbon_id
        """
        agotado_ribbon = self.env.ref('stock_update.ribbon_out_of_stock', raise_if_not_found=False)
        for product in self:
            if product.qty_available <= 0:
                product.allow_out_of_stock_order = False
                if agotado_ribbon:
                    product.website_ribbon_id = agotado_ribbon.id
            else:
                # Opcional: limpiar la etiqueta si vuelve a tener stock
                product.website_ribbon_id = False
