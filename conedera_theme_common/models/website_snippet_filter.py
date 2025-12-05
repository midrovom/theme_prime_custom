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

                # Nombre de la marca
                data['display_name'] = brand.name

                # Imagen de la marca (tu campo dr_image)
                data['image_512'] = brand.dr_image and f'/web/image/product.attribute.value/{brand.id}/dr_image' \
                    or "/web/static/src/img/placeholder.png"

                # Buscar productos publicados que tengan esa marca
                products = request.env['product.template'].search([
                    ('website_published', '=', True),
                    ('dr_brand_value_id', '=', brand.id)
                ])

                # Cantidad de productos asociados
                data['product_count'] = len(products)

                # Lista de productos con info básica
                data['products'] = [{
                    'id': p.id,
                    'name': p.name,
                    'price': p.list_price,
                    'image': f'/web/image/product.template/{p.id}/image_512'
                } for p in products]

        return res
    

    @api.model
    def _get_public_brands(self, mode=None, **kwargs):
        dynamic_filter = self.env.context.get('dynamic_filter') 
        website = self.env['website'].get_current_website()

        # Dominio base: traer solo valores que tengan el check dr_is_brand
        domain = [
            ('dr_is_brand', '=', True),
            ('active', '=', True),
        ]

        # Traer marcas ordenadas por secuencia y nombre
        brands = self.env['product.attribute.value'].search(domain, order="sequence ASC, name ASC")

        return dynamic_filter.with_context()._filter_records_to_values(brands, is_sample=False)
