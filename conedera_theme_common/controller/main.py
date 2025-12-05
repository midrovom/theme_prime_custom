from odoo import http
from odoo.http import request
from collections import defaultdict

class WebsiteSaleBrands(http.Controller):

    @http.route(['/website_sale/get_brands'], type='json', auth='public', website=True)
    def get_dynamic_snippet_brands(self, filter_id=None, limit=None, search_domain=None, with_sample=False):

        domain = [('website_published', '=', True)]
        if search_domain:
            domain += search_domain

        Product = request.env['product.product']
        products = Product.search(domain)

        # Agrupar productos por marca
        brand_map = defaultdict(list)
        for p in products:
            if p.dr_brand_value_id:
                brand_map[p.dr_brand_value_id].append(p)

        result = []

        for brand, prod_list in brand_map.items():
            data = {
                '_record': brand,
                'id': brand.id,
                'display_name': brand.name,
                'product_count': len(prod_list),
                'image_512': brand.image and f"/web/image/product.attribute.value/{brand.id}/image" or '/web/static/src/img/placeholder.png',
                'url': f"/shop?brand_id={brand.id}",
            }
            result.append(data)

        # Aplicar límite
        if limit:
            result = result[:limit]

        return {
            'records': result,
            'is_sample': with_sample,
        }

class WebsiteSaleBrandsFilter(http.Controller):

    @http.route(['/website_sale/brands_filter'], type='json', auth='public', website=True)
    def get_brands_filter(self, filter_name=None):

        domain = [
            ('filter_id.model_id', '=', 'product.attribute.value'),
            ('filter_id.website_id', 'in', (False, request.website.id)),
        ]

        if filter_name:
            domain.append(('filter_id.name', '=', filter_name))

        filters = request.env['website.snippet.filter'].sudo().search(domain, limit=1)

        return filters.id if filters else False
