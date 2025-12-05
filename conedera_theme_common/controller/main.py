from odoo import http
from odoo.http import request


class WebsiteSaleProducts(http.Controller):

    @http.route(['/website_sale/get_products'], type='json', auth='public', website=True)
    def get_dynamic_snippet_products(self, filter_id=None, limit=None, search_domain=None, with_sample=False):
        """
        Returns products with their brand and associated products of that brand
        """
        domain = request.website.sale_get_order() and request.website.website_domain() or []
        
        if search_domain:
            domain += search_domain
        
        # Solo productos publicados en el website
        domain += [('website_published', '=', True)]
        
        Product = request.env['product.product']
        
        if filter_id:
            filter_sudo = request.env['website.snippet.filter'].sudo().browse(int(filter_id))
            if filter_sudo.exists():
                domain += filter_sudo._get_eval_domain()
        
        products = Product.search(domain, limit=limit or 16)
        
        product_data = []
        for product in products:
            brand = getattr(product.product_tmpl_id, 'product_brand_id', False)
            data = {
                '_record': product,
                'display_name': product.display_name,
                'image_512': product.image_512 and f'/web/image/product.product/{product.id}/image_512' or '/web/static/src/img/placeholder.png',
                'image_1920': product.image_1920 and f'/web/image/product.product/{product.id}/image_1920' or '/web/static/src/img/placeholder.png',
                'url': f"/shop/product/{request.env['ir.http']._slug(product.product_tmpl_id)}",
                'price': product.lst_price,
                'default_code': product.default_code,
                'brand': brand.name if brand else False,
                # Productos asociados a la misma marca
                'brand_products': [{
                    'name': p.name,
                    'url': f"/shop/product/{request.env['ir.http']._slug(p.product_tmpl_id)}",
                    'price': p.lst_price,
                    'description': p.product_tmpl_id.description_sale or p.product_tmpl_id.description or '',
                    'image_512': p.image_512 and f'/web/image/product.product/{p.id}/image_512' or '/web/static/src/img/placeholder.png',
                } for p in request.env['product.product'].search([('product_tmpl_id.product_brand_id', '=', brand.id)])] if brand else [],
            }
            product_data.append(data)
        
        return {
            'records': product_data,
            'is_sample': with_sample,
        }


class WebsiteSaleProductsFilter(http.Controller):
    """Controller for product filters"""

    @http.route(['/website_sale/products_filter'], type='json', auth='public', website=True)
    def get_products_filter(self, filter_name=None):
        """Get or create a filter for products"""
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
