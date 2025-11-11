from odoo import _, api, fields, models

import logging

_logger = logging.getLogger(__name__)

class ProductPublicCategory(models.Model):
    _inherit = 'product.public.category'

    @api.model
    def _dynamic_filter_all_categories(self):
        return self.search([])
        # return self.env.ref('advance_theme_front.dynamic_filter_all_categories').id