from odoo import http
from odoo.http import request
from odoo.addons.website.controllers.main import QueryURL

class WebsiteSaleBrands(http.Controller):

    @http.route(['/website_sale/get_brands'], type='json', auth='public', website=True)
    def get_dynamic_snippet_brands(self, filter_id=None, limit=None, search_domain=None, with_sample=False):
        """
        Returns brands for dynamic snippet based on filter and search domain
        """
        domain = []
        if search_domain:
            domain += search_domain

        # Solo valores del atributo "Brand"
        domain += [('attribute_id.name', '=', 'Brand'), ('active', '=', True)]

        BrandValue = request.env['product.attribute.value']

        if filter_id:
            filter_sudo = request.env['website.snippet.filter'].sudo().browse(int(filter_id))
            if filter_sudo.exists():
                domain += filter_sudo._get_eval_domain()

        brands = BrandValue.search(domain, limit=limit or 16)

        # Preparar datos
        brand_data = []
        for brand in brands:
            data = {
                '_record': brand,
                'display_name': brand.name,
                'image_512': brand.image_512 and f'/web/image/product.attribute.value/{brand.id}/image_512' or '/web/static/src/img/placeholder.png',
                'image_1920': brand.image_1920 and f'/web/image/product.attribute.value/{brand.id}/image_1920' or '/web/static/src/img/placeholder.png',
                'url': f'/shop/brand/{brand.id}',
            }
            brand_data.append(data)

        return {
            'records': brand_data,
            'is_sample': with_sample,
        }

class WebsiteSaleBrandsFilter(http.Controller):
    """Controller for brand filters"""

    @http.route(['/website_sale/brands_filter'], type='json', auth='public', website=True)
    def get_brands_filter(self, filter_name=None):
        """Get or create a filter for brands"""
        domain = [
            ('filter_id.model_id', '=', 'product.attribute.value'),
            ('filter_id.website_id', 'in', (False, request.website.id)),
        ]

        if filter_name:
            domain += [('filter_id.name', '=', filter_name)]

        filters = request.env['website.snippet.filter'].sudo().search(domain, limit=1)

        if filters:
            return filters.id

        return False
