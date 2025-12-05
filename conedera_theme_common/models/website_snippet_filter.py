from odoo import api, models
from odoo.http import request

class WebsiteSnippetFilter(models.Model):
    _inherit = 'website.snippet.filter'

    def _filter_records_to_values(self, records, is_sample=False):
        res = super()._filter_records_to_values(records, is_sample)

        # Aplicar solo cuando el snippet está configurado para productos
        if self.model_name == 'product.template':
            for data in res:
                product = data['_record']

                # URL del producto en la tienda
                data['url'] = "/shop/product/%s" % request.env['ir.http']._slug(product)

                # Precio del producto
                data['price'] = product.list_price

                # Imagen por defecto si no tiene
                if not data.get('image_512'):
                    data['image_512'] = "/web/static/img/placeholder.png"

        return res

    @api.model
    def _get_public_products(self, mode=None, **kwargs):
        dynamic_filter = self.env.context.get('dynamic_filter')
        website = self.env['website'].get_current_website()

        # Dominio base: aquí puedes añadir condiciones si quieres
        domain = [
            ('sale_ok', '=', True),  # solo productos vendibles
            ('website_published', '=', True),  # publicados en el sitio web
            ('website_id', 'in', [False, website.id]),  # soporte multi-website
        ]

        # Buscar productos ordenados
        products = self.env['product.template'].search(domain, order="sequence ASC, name ASC")

        return dynamic_filter.with_context()._filter_records_to_values(products, is_sample=False)
