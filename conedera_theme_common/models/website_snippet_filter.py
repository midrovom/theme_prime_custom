import logging
from odoo import api, models

_logger = logging.getLogger(__name__)

class WebsiteSnippetFilter(models.Model):
    _inherit = 'website.snippet.filter'

    def _get_products(self, mode, **kwargs):
        _logger.info("Entrando a _get_products con mode=%s kwargs=%s", mode, kwargs)
        if mode == "by_brand":
            return self._get_products_by_brand(
                brand_id=kwargs.get("product_brand_id"),
                limit=self.env.context.get("limit", self.limit)
            )
        return super()._get_products(mode, **kwargs)

    @api.model
    def _get_products_by_brand(self, brand_id=None, limit=16):
        _logger.info("Ejecutando _get_products_by_brand con brand_id=%s limit=%s", brand_id, limit)

        if not brand_id or brand_id == "all":
            _logger.warning("brand_id vacío o 'all', devolviendo lista vacía")
            return []

        try:
            brand_id = int(brand_id)
        except Exception as e:
            _logger.error("Error convirtiendo brand_id a int: %s", e)
            return []

        domain = [
            ('website_published', '=', True),
            ('dr_brand_value_id', '=', brand_id),
        ]
        _logger.debug("Dominio de búsqueda: %s", domain)

        products = self.env["product.product"].search(domain, limit=limit)
        _logger.info("Productos encontrados: %s", products)

        values = self._filter_records_to_values(products, is_sample=False)
        _logger.info("Valores filtrados: %s", values)

        return values
