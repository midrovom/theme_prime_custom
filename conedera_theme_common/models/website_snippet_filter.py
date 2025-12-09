from odoo import api, models
import logging

_logger = logging.getLogger(__name__)

class WebsiteSnippetFilter(models.Model):
    _inherit = "website.snippet.filter"

    def _filter_records_to_values(self, records, is_sample=False):
        res = super()._filter_records_to_values(records, is_sample)
        if self.model_name == 'product.product':
            for data in res:
                product = data['_record']
                data['url'] = product.website_url or "/shop/product/%s" % product.id
                data['brand'] = product.dr_brand_value_id.name if product.dr_brand_value_id else ""
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

        domain = [
            ('website_published', '=', True),
            ('website_id', 'in', [False, website.id]),
            '|',
            ('dr_brand_value_id', '=', brand_id),
            ('dr_brand_attribute_ids', 'in', [brand_id]),
        ]

        products = self.env['product.product'].sudo().search(domain, order="sequence ASC, name ASC")
        _logger.info("Filtro de marca %s → productos encontrados: %s", brand_id, products.ids)
        return dynamic_filter.with_context()._filter_records_to_values(products, is_sample=False)

# from odoo import api, models
# import logging

# _logger = logging.getLogger(__name__)

# class WebsiteSnippetFilter(models.Model):
#     _inherit = "website.snippet.filter"

#     def _filter_records_to_values(self, records, is_sample=False):
#         res = super()._filter_records_to_values(records, is_sample)
#         if self.model_name == 'product.product':
#             for data in res:
#                 product = data['_record']
#                 data['url'] = product.website_url or "/shop/product/%s" % product.id
#                 data['brand'] = product.dr_brand_value_id.name if product.dr_brand_value_id else ""
#                 if not data.get('image_512'):
#                     data['image_512'] = "/web/static/img/placeholder.png"
#         return res

#     @api.model
#     def _get_products_by_brand(self, mode=None, **kwargs):
#         dynamic_filter = self.env.context.get('dynamic_filter')
#         website = self.env['website'].get_current_website()
#         brand_id = kwargs.get("product_brand_id") or self.env.context.get("product_brand_id")

#         if not brand_id or brand_id == "all":
#             return []

#         try:
#             brand_id = int(brand_id)
#         except Exception:
#             return []

#         domain = [
#             ('website_published', '=', True),
#             ('website_id', 'in', [False, website.id]),
#             ('dr_brand_value_id', '=', brand_id),
#         ]
#         products = self.env['product.product'].sudo().search(domain, order="sequence ASC, name ASC")
#         return dynamic_filter.with_context()._filter_records_to_values(products, is_sample=False)
