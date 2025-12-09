from odoo import api, models
import logging

_logger = logging.getLogger(__name__)

class WebsiteSnippetFilter(models.Model):
    _inherit = "website.snippet.filter"

    @api.model
    def _get_products_by_brand(self, brand_id=None, limit=16):
        brand_id = brand_id or self.env.context.get("product_brand_id")
        if not brand_id or brand_id == "all":
            return []

        try:
            brand_id = int(brand_id)
        except Exception:
            return []

        domain = [
            ("website_published", "=", True),
            ("dr_brand_value_id", "=", brand_id),
        ]

        # Buscar primero en product.product
        products = self.env["product.product"].sudo().search(domain, limit=limit)
        _logger.info(">>> Productos encontrados en product.product: %s", products.ids)

        if products:
            return self._convert_brand_products_to_values(products)

        # Si no hay variantes, buscar en product.template
        templates = self.env["product.template"].sudo().search(domain, limit=limit)
        _logger.info(">>> Productos encontrados en product.template: %s", templates.ids)

        return self._convert_brand_templates_to_values(templates)

    def _convert_brand_products_to_values(self, products):
        result = []
        for prod in products:
            data = {
                "_record": prod,
                "id": prod.id,
                "display_name": prod.display_name,
                "image_512": prod.image_512
                    and f"/web/image/product.product/{prod.id}/image_512"
                    or "/web/static/img/placeholder.png",
                "brand": prod.dr_brand_value_id.name or "",
            }
            result.append(data)
        return result

    def _convert_brand_templates_to_values(self, templates):
        result = []
        for tmpl in templates:
            data = {
                "_record": tmpl,
                "id": tmpl.id,
                "display_name": tmpl.name,
                "image_512": tmpl.image_512
                    and f"/web/image/product.template/{tmpl.id}/image_512"
                    or "/web/static/img/placeholder.png",
                "brand": tmpl.dr_brand_value_id.name or "",
            }
            result.append(data)
        return result

    def _get_products(self, mode, **kwargs):
        _logger.info(">>> _get_products() llamado con mode=%s", mode)
        _logger.info(">>> _get_products() kwargs=%s", kwargs)
        _logger.info(">>> _get_products() context=%s", self.env.context)

        if mode == "by_brand":
            brand_id = kwargs.get("product_brand_id") or self.env.context.get("product_brand_id")
            _logger.info(">>> _get_products() brand_id recibido=%s", brand_id)

            result = self._get_products_by_brand(
                brand_id,
                limit=self.env.context.get("limit", self.limit)
            )
            _logger.info(">>> _get_products() resultado by_brand=%s", result)
            return result

        result = super()._get_products(mode, **kwargs)
        _logger.info(">>> _get_products() resultado super=%s", result)
        return result
