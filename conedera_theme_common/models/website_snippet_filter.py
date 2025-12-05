from odoo import _, api, fields, models
from odoo.http import request

import logging

_logger = logging.getLogger(__name__)

class WebsiteSnippetFilter(models.Model):
    _inherit = 'website.snippet.filter'
    
    def _filter_records_to_values(self, records, is_sample=False):
        res = super()._filter_records_to_values(records, is_sample)

        # Aplicar solo cuando el snippet está configurado para marcas
        if self.model_name == 'product.attribute.value':
            for data in res:
                brand = data['_record']

                # URL personalizada para la marca
                data['url'] = "/shop/brand/%s" % brand.id

                # Buscar productos publicados que tengan esa marca
                products = request.env['product.template'].search([
                    ('website_published', '=', True),
                    ('product_template_attribute_value_ids', 'in', brand.ids)
                ])

                # Cantidad de productos asociados
                data['product_count'] = len(products)

                # Imagen de la marca (si existe, sino placeholder)
                if not data.get('image_512'):
                    data['image_512'] = f"/web/image/product.attribute.value/{brand.id}/image_512" \
                        if brand.image_512 else "/web/static/src/img/placeholder.png"

        return res
    

    @api.model
    def _get_public_brands(self, mode=None, **kwargs):
        dynamic_filter = self.env.context.get('dynamic_filter') 
        website = self.env['website'].get_current_website()

        # Dominio base: solo valores del atributo "Brand"
        domain = [
            ('attribute_id.name', '=', 'Brand'),
            ('active', '=', True),
        ]

        # Traer marcas ordenadas por secuencia y nombre
        brands = self.env['product.attribute.value'].search(domain, order="sequence ASC, name ASC")

        return dynamic_filter.with_context()._filter_records_to_values(brands, is_sample=False)
