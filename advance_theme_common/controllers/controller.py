from odoo import http
from odoo.http import request

class WebsiteCategorySnippet(http.Controller):

    @http.route('/website/snippet/categories', type='json', auth='public')
    def categories_handler(self, domain=None):
        categories = request.env['product.public.category'].sudo().search(domain or [], limit=12)
        return [{
            "name": cat.name,
            "url": f"/shop/category/{cat.id}",
            "image": f"/web/image/product.public.category/{cat.id}/image_1920"
        } for cat in categories]
    

from odoo import http
from odoo.http import request
from odoo.addons.website.controllers.main import QueryURL


class WebsiteSaleCategories(http.Controller):

    @http.route(['/website_sale/get_categories'], type='json', auth='public', website=True)
    def get_dynamic_snippet_categories(self, filter_id=None, limit=None, search_domain=None, with_sample=False):
        """
        Returns categories for dynamic snippet based on filter and search domain
        """
        domain = request.website.sale_get_order() and request.website.website_domain() or []
        
        if search_domain:
            domain += search_domain
        
        # Always show only published categories
        domain += [('website_published', '=', True)]
        
        Category = request.env['product.public.category']
        
        if filter_id:
            filter_sudo = request.env['website.snippet.filter'].sudo().browse(int(filter_id))
            if filter_sudo.exists():
                domain += filter_sudo._get_eval_domain()
        
        categories = Category.search(domain, limit=limit or 16)
        
        # Prepare data
        category_data = []
        for category in categories:
            data = {
                '_record': category,
                'display_name': category.display_name,
                'image_512': category.image_512 and f'/web/image/product.public.category/{category.id}/image_512' or '/web/static/src/img/placeholder.png',
                'image_1920': category.image_1920 and f'/web/image/product.public.category/{category.id}/image_1920' or '/web/static/src/img/placeholder.png',
                'url': f'/shop/category/{category.id}',
            }
            category_data.append(data)
        
        return {
            'records': category_data,
            'is_sample': with_sample,
        }


class WebsiteSaleCategoriesFilter(http.Controller):
    """Controller for category filters"""

    @http.route(['/website_sale/categories_filter'], type='json', auth='public', website=True)
    def get_categories_filter(self, filter_name=None):
        """Get or create a filter for categories"""
        domain = [
            ('filter_id.model_id', '=', 'product.public.category'),
            ('filter_id.website_id', 'in', (False, request.website.id)),
        ]
        
        if filter_name:
            domain += [('filter_id.name', '=', filter_name)]
        
        filters = request.env['website.snippet.filter'].sudo().search(domain, limit=1)
        
        if filters:
            return filters.id
        
        return False