from odoo import _, api, fields, models
from odoo.http import request

class WebsiteSnippetFilter(models.Model):
    _inherit = 'website.snippet.filter'

    def _filter_records_to_values(self, records, is_sample=False):
        res = super()._filter_records_to_values(records, is_sample)

        # SOLO aplicar si se trata de brands
        if self.model_name == 'product.attribute.value':
            for data in res:
                brand = data['_record']

                # URL SEO de la marca
                data['url'] = "/shop?brand_id=%s" % brand.id

                # Buscar productos publicados para esta marca
                products = request.env['product.template'].search([
                    ('website_published', '=', True),
                    ('product_template_attribute_value_ids', 'in', brand.id)
                ])

                # Cantidad de productos
                data['product_count'] = len(products)

                # Imagen de la marca si existe
                if brand.image:
                    data['image_512'] = "/web/image/product.attribute.value/%s/image" % brand.id
                else:
                    data['image_512'] = "/web/static/img/placeholder.png"

        return res

    @api.model
    def _get_public_brands(self, mode=None, **kwargs):
        dynamic_filter = self.env.context.get('dynamic_filter')
        website = self.env['website'].get_current_website()

        # Dominio para obtener SOLO marcas usadas en productos y publicadas en web
        domain = [
            ('attribute_id.name', '=', 'Brand'),
            ('is_used_on_products', '=', True),
            ('active', '=', True),
        ]

        # Obtener las marcas
        brands = self.env['product.attribute.value'].search(domain, order="sequence ASC, name ASC")

        # Formatear datos para el snippet
        return dynamic_filter.with_context()._filter_records_to_values(brands, is_sample=False)
