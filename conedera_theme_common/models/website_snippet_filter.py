from odoo import api, models

class WebsiteSnippetFilter(models.Model):
    _inherit = 'website.snippet.filter'

    def _get_products(self, mode, **kwargs):
        if mode == "by_brand":
            return self._get_products_by_brand(
                brand_id=kwargs.get("product_brand_id"),
                limit=self.env.context.get("limit", self.limit)
            )
        return super()._get_products(mode, **kwargs)

    @api.model
    def _get_products_by_brand(self, brand_id=None, limit=16):
        if not brand_id or brand_id == "all":
            return []

        try:
            brand_id = int(brand_id)
        except Exception:
            return []

        domain = [
            ('website_published', '=', True),
            ('dr_brand_value_id', '=', brand_id),
        ]

        products = self.env["product.product"].search(domain, limit=limit)

        return self._filter_records_to_values(products, is_sample=False)
