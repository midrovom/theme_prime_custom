from odoo import http
from odoo.http import request

class WebsiteSaleProductsByBrand(http.Controller):

    @http.route(['/website_sale/get_products_by_brand'], type='json', auth='public', website=True)
    def get_products_by_brand(self, brand_id=None, limit=16, search_domain=None, with_sample=False):
        """
        Retorna productos filtrados por la marca seleccionada en el builder.
        """
        domain = [('website_published', '=', True)]
        if search_domain:
            domain += search_domain

        # Invoca el método del modelo heredado
        products = request.env['website.snippet.filter']._get_products_by_brand(
            request.website,
            limit,
            domain,
            brand_id=brand_id
        )

        # Preparar datos para el snippet
        product_data = []
        for product in products:
            data = {
                '_record': product,
                'display_name': product.name,
                'description_sale': product.description_sale or '',
                'image_512': product.image_512 and f'/web/image/product.template/{product.id}/image_512' or '/web/static/src/img/placeholder.png',
                'url': f'/shop/product/{product.id}',
            }
            product_data.append(data)

        return {
            'records': product_data,
            'is_sample': with_sample,
        }
