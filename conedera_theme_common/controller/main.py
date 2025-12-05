from odoo import http
from odoo.http import request
from odoo.addons.website.controllers.main import QueryURL
class WebsiteSaleBrands(http.Controller):

    @http.route(['/website_sale/get_brands'], type='json', auth='public', website=True)
    def get_dynamic_snippet_brands(self, filter_id=None, limit=None, search_domain=None, with_sample=False):
        """
        Returns BRANDS for dynamic snippet based on filter and search domain
        """
        domain = request.website.sale_get_order() and request.website.website_domain() or []

        if search_domain:
            domain += search_domain

        # Always show only published brands (assuming you have this field)
        domain += [('website_published', '=', True)]

        Brand = request.env['dr.brand.value']

        # Apply snippet filter if provided
        if filter_id:
            filter_sudo = request.env['website.snippet.filter'].sudo().browse(int(filter_id))
            if filter_sudo.exists():
                domain += filter_sudo._get_eval_domain()

        brands = Brand.search(domain, limit=limit or 16)

        # Prepare JSON output
        brand_data = []
        for brand in brands:
            data = {
                '_record': brand,
                'display_name': brand.display_name,
                'image_512': brand.image_512 and f'/web/image/dr.brand.value/{brand.id}/image_512' or '/web/static/src/img/placeholder.png',
                'image_1920': brand.image_1920 and f'/web/image/dr.brand.value/{brand.id}/image_1920' or '/web/static/src/img/placeholder.png',
                'url': f'/shop/brand/{request.env["ir.http"]._slug(brand)}',
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
        """
        Get or create a filter for BRANDS
        """

        domain = [
            ('filter_id.model_id', '=', 'dr.brand.value'),   # Modelo de marcas
            ('filter_id.website_id', 'in', (False, request.website.id)),
        ]

        if filter_name:
            domain += [('filter_id.name', '=', filter_name)]

        filters = request.env['website.snippet.filter'].sudo().search(domain, limit=1)

        if filters:
            return filters.id

        return False
