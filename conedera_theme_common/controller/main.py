from odoo import http
from odoo.http import request

class WebsiteBrandProducts(http.Controller):

    @http.route('/shop/get_products_by_brand', type='json', auth='public', website=True)
    def get_products_by_brand(self, brand_id):
        products = request.env['product.template'].search([
            ('brand_id', '=', int(brand_id)),
            ('website_published', '=', True)
        ])

        html = request.env.ref(
            "conedera_theme_common.products_list_template"
        )._render({"products": products})

        return {"html": html}
