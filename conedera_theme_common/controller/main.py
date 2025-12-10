from odoo import http
from odoo.http import request
from odoo.addons.website_sale.controllers.snippets import WebsiteSaleSnippetProducts

class WebsiteSaleSnippetProductsBrand(WebsiteSaleSnippetProducts):

    def _get_search_domain(self, options):
        # Llamamos al original
        domain = super()._get_search_domain(options)

        # Añadimos filtro por marca si existe
        product_brand_id = options.get('productBrandId')
        if product_brand_id and product_brand_id != 'all':
            domain.append(('dr_brand_value_id', '=', int(product_brand_id)))

        return domain
