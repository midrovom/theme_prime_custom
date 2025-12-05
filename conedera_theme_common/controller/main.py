from odoo import http
from odoo.http import request
from odoo.addons.website.controllers.main import QueryURL

class WebsiteSaleBrandsFilter(http.Controller):

    @http.route(['/website_sale/brands_filter'], type='json', auth='public', website=True)
    def get_brands_filter(self, filter_name=None):
        """
        Get or create a filter for brands.
        A brand is represented by `product.attribute.value` with attribute = 'Brand'.
        """

        # Dominio base: queremos un filtro configurado para product.attribute.value
        domain = [
            ('filter_id.model_id', '=', 'product.attribute.value'),
            ('filter_id.website_id', 'in', (False, request.website.id)),
        ]

        # Si el usuario pasa el nombre del filtro, añadimos esa condición
        if filter_name:
            domain.append(('filter_id.name', '=', filter_name))

        # Buscamos un filtro existente
        filter_rec = request.env['website.snippet.filter'].sudo().search(domain, limit=1)

        if filter_rec:
            return filter_rec.id

        return False
