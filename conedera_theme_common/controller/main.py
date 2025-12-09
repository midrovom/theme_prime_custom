from odoo import http
from odoo.http import request

class WebsiteSaleBrands(http.Controller):

    @http.route(['/website_sale/get_brands'], type='json', auth='public', website=True)
    def get_dynamic_snippet_brands(self, filter_id=None, limit=None, search_domain=None, with_sample=False):
        """
        Returns products for dynamic snippet based on brand filter and search domain
        """
        domain = request.website.sale_get_order() and request.website.website_domain() or []
        
        if search_domain:
            domain += search_domain
        
        # Always show only published products
        domain += [('website_published', '=', True)]
        
        Product = request.env['product.product']
        
        if filter_id:
            filter_sudo = request.env['website.snippet.filter'].sudo().browse(int(filter_id))
            if filter_sudo.exists():
                domain += filter_sudo._get_eval_domain()
        
        products = Product.search(domain, limit=limit or 16)
        
        # Prepare data
        brand_data = []
        for product in products:
            data = {
                '_record': product,
                'display_name': product.display_name,
                'image_512': product.image_512 and f'/web/image/product.product/{product.id}/image_512' or '/web/static/src/img/placeholder.png',
                'image_1920': product.image_1920 and f'/web/image/product.product/{product.id}/image_1920' or '/web/static/src/img/placeholder.png',
                'url': product.website_url or f'/shop/product/{product.id}',
            }
            brand_data.append(data)
        
        return {
            'records': brand_data,
            'is_sample': with_sample,
        }
class WebsiteSaleBrandsFilter(http.Controller):

    @http.route(['/website_sale/brand_filter'], type='json', auth='public', website=True)
    def get_brands_filter(self, filter_name=None):
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
