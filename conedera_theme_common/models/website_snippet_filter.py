from odoo import models

class WebsiteSnippetFilter(models.Model):
    _inherit = 'website.snippet.filter'

    def _filter_records_to_values(self, records, is_sample=False):
        res = super()._filter_records_to_values(records, is_sample)
        if self.model_name == 'product.template':
            brand_id = self.snippet_data.get('productBrandId')
            if brand_id:
                # Filtrar productos de esa marca
                res = [r for r in res if brand_id in r['_record'].product_template_attribute_value_ids.ids]

                # Añadir información de la marca (imagen + nombre)
                brand = self.env['product.attribute.value'].browse(int(brand_id))
                for r in res:
                    r['brand_name'] = brand.name
                    r['brand_image'] = brand.image_1920  # campo binario de imagen
        return res


# from odoo import api, models, fields
# from odoo.http import request

# class WebsiteSnippetFilter(models.Model):
#     _inherit = 'website.snippet.filter'

#     def _filter_records_to_values(self, records, is_sample=False):
#         res = super()._filter_records_to_values(records, is_sample)

#         # Aplicar solo cuando el filtro es de MARCAS
#         is_brand_filter = (
#             self.filter_id
#             and self.filter_id.model_id
#             and self.filter_id.model_id.model == 'product.attribute.value'
#         )

#         if not is_brand_filter:
#             return res

#         Product = self.env['product.template']

#         for data in res:
#             brand = data['_record']

#             # URL SEO hacia los productos filtrados por marca
#             data['url'] = "/shop?brand_id=%s" % brand.id

#             # Buscar productos publicados
#             product_domain = [
#                 ('website_published', '=', True),
#                 ('product_template_attribute_value_ids', 'in', brand.id)
#             ]

#             products = Product.search(product_domain)

#             data['product_count'] = len(products)

#             # Imagen del modelo (image_512 disponible en Odoo 18)
#             if brand.image_512:
#                 data['image_512'] = "/web/image/product.attribute.value/%s/image_512" % brand.id
#             else:
#                 data['image_512'] = "/web/static/src/img/placeholder.png"

#         return res

#     @api.model
#     def _get_public_brands(self, mode=None, **kwargs):
#         website = self.env['website'].get_current_website()

#         # Dominio seguro para obtener solo MARCAS reales
#         domain = [
#             ('attribute_id.name', '=', 'Brand'),
#             ('active', '=', True),
#         ]

#         # Si tu instancia tiene el campo is_used_on_products, úsalo
#         if 'is_used_on_products' in self.env['product.attribute.value']._fields:
#             domain.append(('is_used_on_products', '=', True))

#         # Obtener marcas (ordenadas)
#         brands = self.env['product.attribute.value'].sudo().search(
#             domain, order="sequence ASC, name ASC"
#         )

#         dynamic_filter = self.env.context.get('dynamic_filter', self)

#         # Formatear valores
#         return dynamic_filter.with_context()._filter_records_to_values(
#             brands, is_sample=False
#         )
