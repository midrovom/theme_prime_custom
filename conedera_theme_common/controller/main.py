from odoo import http
from odoo.http import request

class WebsiteSaleBrands(http.Controller):

    @http.route(['/website_sale/get_products_by_brand'], type='json', auth='public', website=True)
    def get_products_by_brand(self, brand_id=None, limit=16):
        snippet_filter = request.env['website.snippet.filter'].sudo()
        return {
            'records': snippet_filter._get_products_by_brand(brand_id, limit),
            'is_sample': False,
        }
