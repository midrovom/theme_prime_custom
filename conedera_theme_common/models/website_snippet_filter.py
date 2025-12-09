from odoo import api, models
import logging

_logger = logging.getLogger(__name__)

class WebsiteSnippetFilter(models.Model):
    _inherit = 'website.snippet.filter'

    @api.model
    def _get_products_by_brand(self, brand_id=None, limit=16):
        brand_id = brand_id or self.env.context.get("product_brand_id")

        _logger.info(">>> _get_products_by_brand() brand_id=%s", brand_id)

        if not brand_id or brand_id == "all":
            _logger.warning(">>> brand_id vacío o 'all', devolviendo vacio")
            return []

        try:
            brand_id = int(brand_id)
        except Exception:
            _logger.error(">>> Error convirtiendo brand_id=%s", brand_id)
            return []

        domain = [
            ("website_published", "=", True),
            ("dr_brand_value_id", "=", brand_id),
        ]

        products = self.env["product.product"].sudo().search(domain, limit=limit)

        _logger.info(">>> Productos encontrados para brand %s: %s", brand_id, products.ids)

        return self._filter_records_to_values(products, is_sample=False)

    def _get_products(self, mode, **kwargs):
        if mode == "by_brand":
            return self._get_products_by_brand(
                kwargs.get("product_brand_id"),
                limit=self.env.context.get("limit", self.limit),
            )
        return super()._get_products(mode, **kwargs)
