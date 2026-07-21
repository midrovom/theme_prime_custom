from odoo import models
import logging

_logger = logging.getLogger(__name__)

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    @api.depends('qty_available')
    def _compute_stock_flags(self):
        agotado_ribbon = self.env.ref('tu_modulo.ribbon_out_of_stock', raise_if_not_found=False)
        for product in self:
            if product.qty_available <= 0:
                product.allow_out_of_stock_order = False
                if agotado_ribbon:
                    product.website_ribbon_id = agotado_ribbon.id
            else:
                product.website_ribbon_id = False
