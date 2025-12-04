from odoo import models, api
from odoo.osv import expression

class WebsiteSnippetFilter(models.Model):
    _inherit = 'website.snippet.filter'

    @api.model
    def _get_products_by_brand(self, brand_id, limit=None, **kwargs):
        website = self.env['website'].get_current_website()
        domain = [
            ('website_published', '=', True),
            ('sale_ok', '=', True),
            ('website_id', 'in', [False, website.id]),
        ]
        if brand_id:
            domain.append(('product_tmpl_id.brand_id', '=', brand_id))
        products = self.env['product.product'].search(domain, limit=limit or self.limit)
        return self._filter_records_to_values(products, is_sample=False)
