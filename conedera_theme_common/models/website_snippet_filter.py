from odoo import api, models
from odoo.http import request
import logging

_logger = logging.getLogger(__name__)

class WebsiteSnippetFilter(models.Model):
    _inherit = "website.snippet.filter"

    def _filter_records_to_values(self, records, is_sample=False):
        res = super()._filter_records_to_values(records, is_sample)
        if self.model_name == 'product.product':
            for data in res:
                product = data['_record']

                # Asegurar que tenga URL
                data['url'] = product.website_url or "/shop/product/%s" % product.id

                # Si deseas incluir la marca
                data['brand'] = product.dr_brand_value_id.name if product.dr_brand_value_id else ""

                # Imagen por defecto si no tiene
                if not data.get('image_512'):
                    data['image_512'] = "/web/static/img/placeholder.png"

        return res

    @api.model
    def _get_products_by_brand(self, mode=None, **kwargs):
        dynamic_filter = self.env.context.get('dynamic_filter')
        website = self.env['website'].get_current_website()

        brand_id = kwargs.get("product_brand_id") or self.env.context.get("product_brand_id")

        if not brand_id or brand_id == "all":
            return []

        try:
            brand_id = int(brand_id)
        except Exception:
            return []

        # Dominio base: productos publicados en el website actual
        domain = [
            ('website_published', '=', True),
            ('website_id', 'in', [False, website.id]),
            ('dr_brand_value_id', '=', brand_id),
        ]

        products = self.env['product.product'].sudo().search(domain, order="sequence ASC, name ASC")

        return dynamic_filter.with_context()._filter_records_to_values(products, is_sample=False)

# from odoo import api, models
# import logging

# _logger = logging.getLogger(__name__)


# class WebsiteSnippetFilter(models.Model):
#     _inherit = "website.snippet.filter"

#     @api.model
#     def _get_products_by_brand(self, brand_id=None, limit=16):
#         brand_id = brand_id or self.env.context.get("product_brand_id")
#         if not brand_id or brand_id == "all":
#             return []

#         try:
#             brand_id = int(brand_id)
#         except Exception:
#             return []

#         domain = [
#             ("website_published", "=", True),
#             ("product_template_attribute_value_ids.attribute_value_id", "=", brand_id),
#         ]

#         products = self.env["product.product"].sudo().search(domain, limit=limit)
#         return self._convert_brand_products_to_values(products)

#     def _convert_brand_products_to_values(self, products):
#         result = []
#         for prod in products:
#             data = {
#                 "_record": prod,
#                 "id": prod.id,
#                 "display_name": prod.display_name,
#                 "image_512": prod.image_512
#                     and f"/web/image/product.product/{prod.id}/image_512"
#                     or "/web/static/img/placeholder.png",
#                 "brand": prod.dr_brand_value_id.name if prod.dr_brand_value_id else "",
#             }
#             result.append(data)
#         return result

#     def _get_products(self, mode, **kwargs):
#         _logger.info(">>> _get_products() llamado con mode=%s", mode)
#         _logger.info(">>> _get_products() kwargs=%s", kwargs)
#         _logger.info(">>> _get_products() context=%s", self.env.context)

#         if mode == "by_brand":
#             brand_id = (
#                 kwargs.get("product_brand_id")
#                 or self.env.context.get("product_brand_id")
#             )

#             _logger.info(">>> _get_products() brand_id recibido=%s", brand_id)

#             result = self._get_products_by_brand(
#                 brand_id, limit=self.env.context.get("limit", self.limit)
#             )
#             _logger.info(">>> _get_products() resultado by_brand=%s", result)
#             return result

#         result = super()._get_products(mode, **kwargs)
#         _logger.info(">>> _get_products() resultado super=%s", result)
#         return result
