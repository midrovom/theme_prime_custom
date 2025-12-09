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
            ("attribute_line_ids.value_ids", "=", brand_id),
        ]

        templates = self.env["product.template"].sudo().search(domain, limit=limit)
        _logger.info(">>> Productos encontrados en product.template: %s", templates.ids)

        return self._convert_brand_templates_to_values(templates)

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
                "brand": ", ".join(tmpl.attribute_line_ids.filtered(
                    lambda l: l.attribute_id.name == "Brand"
                ).mapped("value_ids.name")),
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
