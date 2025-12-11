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

                # Extraer la marca desde los atributos del template
                brand_name = ""
                tmpl = product.product_tmpl_id
                for val in tmpl.attribute_line_ids.mapped('value_ids'):
                    if val.attribute_id.dr_is_brand:
                        brand_name = val.name
                        break
                data['brand'] = brand_name

                if not data.get('image_512'):
                    data['image_512'] = "/web/static/img/placeholder.png"
        return res

    @api.model
    def _get_products_by_brand(self, mode=None, **kwargs):
        _logger.info(">>> Entrando a _get_products_by_brand con kwargs=%s y context=%s", kwargs, self.env.context)

        dynamic_filter = self.env.context.get('dynamic_filter')
        website = self.env['website'].get_current_website()

        brand_id = kwargs.get("product_brand_id") or self.env.context.get("product_brand_id")

        if not brand_id or brand_id == "all":
            _logger.info(">>> No se recibió brand_id válido, devolviendo lista vacía")
            return []

        try:
            brand_id = int(brand_id)
        except Exception as e:
            _logger.warning(">>> Error convirtiendo brand_id a int: %s", e)
            return []

        # Buscar en product.template
        domain = [
            ('website_published', '=', True),
            ('website_id', 'in', [False, website.id]),
            ('attribute_line_ids.value_ids', 'in', [brand_id]),
        ]
        _logger.info(">>> Dominio de búsqueda (template): %s", domain)

        products_tmpl = self.env['product.template'].sudo().search(domain, order="sequence ASC, name ASC")
        products = products_tmpl.mapped('product_variant_ids')
        _logger.info(">>> Productos encontrados para brand_id=%s: %s", brand_id, products.ids)

        values = dynamic_filter.with_context()._filter_records_to_values(products, is_sample=False)
        _logger.info(">>> Valores devueltos al snippet: %s", values)
        return values

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
#         _logger.info(">>> Entrando a _get_products_by_brand con kwargs=%s y context=%s", kwargs, self.env.context)

#         dynamic_filter = self.env.context.get('dynamic_filter')
#         website = self.env['website'].get_current_website()

#         brand_id = kwargs.get("product_brand_id") or self.env.context.get("product_brand_id")

#         # Si no llega por kwargs/context, intentar extraerlo del search_domain
#         if not brand_id:
#             search_domain = self.env.context.get('search_domain', [])
#             for cond in search_domain:
#                 if cond[0] == 'dr_brand_value_id' and cond[1] == '=':
#                     brand_id = cond[2]

#         _logger.info(">>> brand_id final: %s", brand_id)

#         if not brand_id or brand_id == "all":
#             _logger.info(">>> No se recibió brand_id válido, devolviendo lista vacía")
#             return []

#         try:
#             brand_id = int(brand_id)
#         except Exception as e:
#             _logger.warning(">>> Error convirtiendo brand_id a int: %s", e)
#             return []

#         domain = [
#             ('website_published', '=', True),
#             ('website_id', 'in', [False, website.id]),
#             ('dr_brand_value_id', '=', brand_id),
#         ]
#         _logger.info(">>> Dominio de búsqueda: %s", domain)

#         products = self.env['product.product'].sudo().search(domain, order="sequence ASC, name ASC")
#         _logger.info(">>> Productos encontrados para brand_id=%s: %s", brand_id, products.ids)

#         values = dynamic_filter.with_context()._filter_records_to_values(products, is_sample=False)
#         _logger.info(">>> Valores devueltos al snippet: %s", values)
#         return values
