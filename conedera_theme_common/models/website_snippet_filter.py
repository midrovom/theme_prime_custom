from odoo import _, api, fields, models
from odoo.http import request

class WebsiteSnippetFilter(models.Model):
    _inherit = 'website.snippet.filter'

    def _filter_records_to_values(self, records, is_sample=False):
        res = super()._filter_records_to_values(records, is_sample)

        # SOLO aplicar cuando el snippet esté configurado para marcas
        if self.model_name == 'dr.brand.value':
            for data in res:
                brand = data['_record']

                # URL amigable para marca
                data['url'] = "/shop/brand/%s" % request.env['ir.http']._slug(brand)

                # productos asociados a la marca
                products = self.env['product.template'].search([
                    ('dr_brand_value_id', '=', brand.id),
                    ('website_published', '=', True)
                ])

                data['products'] = [{
                    'id': p.id,
                    'name': p.name,
                    'price': p.list_price,
                    'image_512': p.image_512 or "/web/static/img/placeholder.png",
                    'url': p.website_url,
                } for p in products]

                data['product_count'] = len(products)

                # Imagen de marca si no tiene
                if not data.get('image_512'):
                    data['image_512'] = "/web/static/img/placeholder.png"

        return res

    # Nuevo método para traer marcas en lugar de categorías
    @api.model
    def _get_public_brands(self, mode=None, **kwargs):

        dynamic_filter = self.env.context.get('dynamic_filter')
        website = self.env['website'].get_current_website()

        # Dominio base (ajustable según tu modelo)
        domain = [
            ('is_show', '=', True),    # Campo equivalente al que usabas para categoría
            ('website_id', 'in', [False, website.id]), 
        ]

        # Buscar marcas ordenadas
        brands = self.env['dr.brand.value'].search(domain, order="sequence ASC, name ASC")

        # Convertir al formato esperado por el snippet
        return dynamic_filter.with_context()._filter_records_to_values(brands, is_sample=False)
