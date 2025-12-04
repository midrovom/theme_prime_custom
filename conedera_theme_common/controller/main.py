from odoo import http
from odoo.http import request

class WebsiteBrandProducts(http.Controller):

    @http.route('/website/snippet/brand/products', type='json', auth='public')
    def brand_products(self, brand_id=None, limit=12):
        Brand = request.env['product.brand'].sudo()

        if not brand_id:
            return []

        products = request.env['product.template'].sudo().search([
            ('brand_id', '=', int(brand_id)),
            ('website_published', '=', True),
        ], limit=limit)

        return [{
            "name": p.name,
            "price": p.website_price,
            "url": f"/shop/product/{p.id}",
            "image": f"/web/image/product.template/{p.id}/image_1920",
        } for p in products]
