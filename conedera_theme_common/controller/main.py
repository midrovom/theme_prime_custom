from odoo import http
from odoo.http import request
from odoo.addons.website.controllers.main import QueryURL

class WebsiteSaleCategoriesFilter(http.Controller):
    """Controller for category filters"""

    @http.route(['/website_sale/brand_filter'], type='json', auth='public', website=True)
    def get_categories_filter(self, filter_name=None):
        """Get or create a filter for categories"""
        domain = [
            ('filter_id.model_id', '=', 'product.product'),
            ('filter_id.website_id', 'in', (False, request.website.id)),
        ]
        
        if filter_name:
            domain += [('filter_id.name', '=', filter_name)]
        
        filters = request.env['website.snippet.filter'].sudo().search(domain, limit=1)
        
        if filters:
            return filters.id
        
        return False