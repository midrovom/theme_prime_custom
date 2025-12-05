from odoo import http
from odoo.http import request

class WebsiteSaleBrandsFilter(http.Controller):

    @http.route(['/website_sale/brands_filter'], type='json', auth='public', website=True)
    def get_brands_filter(self, filter_name=None):
        """Return filter that is configured for BRAND selection."""

        domain = [
            ('filter_id.model_id', '=', 'product.attribute.value'),  # Marca
            ('filter_id.website_id', 'in', (False, request.website.id)),
            ('filter_id.attribute_id.name', '=', 'Brand'),
        ]

        if filter_name:
            domain.append(('filter_id.name', '=', filter_name))

        flt = request.env['website.snippet.filter'].sudo().search(domain, limit=1)

        if flt:
            return flt.id
        
        return False

class WebsiteSaleProductsByBrand(http.Controller):

    @http.route(['/website_sale/get_products_by_brand'], type='json', auth='public', website=True)
    def get_dynamic_snippet_products_by_brand(self, filter_id=None, limit=None, search_domain=None, with_sample=False):
        """
        Returns PRODUCT records filtered by BRAND for the dynamic snippet.
        """

        domain = [('website_published', '=', True)]

        # Extra domain from the snippet (search bar, etc)
        if search_domain:
            domain += search_domain

        # Filter selected → must apply brand filter
        if filter_id:
            filter_sudo = request.env['website.snippet.filter'].sudo().browse(int(filter_id))
            if filter_sudo.exists():

                # The filter contains domain for product.attribute.value (brands)
                brand_domain = filter_sudo._get_eval_domain()

                brand_ids = request.env['product.attribute.value'].search(brand_domain).ids

                # Convert brand domain → product domain
                domain.append(('product_template_attribute_value_ids', 'in', brand_ids))

        Product = request.env['product.template']

        products = Product.search(domain, limit=limit or 16)

        # Prepare data expected by product_product template
        data_products = []
        for product in products:
            data_products.append({
                '_record': product,
                'id': product.id,
                'display_name': product.display_name,
                'website_url': product.website_url,
                'image_512': product.image_512,
                'image_1920': product.image_1920,
                'rating_avg': product.rating_avg,
                'rating_count': product.rating_count,
            })

        return {
            'records': data_products,
            'is_sample': with_sample,
        }
