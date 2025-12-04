from odoo import http
from odoo.http import request
from odoo.osv import expression

class WebsiteSaleBrands(http.Controller):

    @http.route(['/website_sale/get_brands'], type='json', auth='public', website=True)
    def get_dynamic_snippet_brands(self, filter_id=None, limit=None, search_domain=None, brand_id=None, with_sample=False):
        """
        Devuelve productos de una marca específica para el snippet dinámico
        """
        domain = request.website.website_domain() or []

        if search_domain:
            domain += search_domain

        # Siempre mostrar solo productos publicados y vendibles
        domain += [('website_published', '=', True), ('sale_ok', '=', True)]

        Product = request.env['product.product']

        # Si hay un filtro configurado en website.snippet.filter
        if filter_id:
            filter_sudo = request.env['website.snippet.filter'].sudo().browse(int(filter_id))
            if filter_sudo.exists():
                domain += filter_sudo._get_eval_domain()

        # Si se seleccionó una marca específica
        if brand_id:
            domain += [('product_tmpl_id.brand_id', '=', int(brand_id))]

        products = Product.sudo().search(domain, limit=limit or 16)

        # Preparar datos para el snippet
        product_data = []
        for product in products:
            data = {
                '_record': product,
                'display_name': product.display_name,
                'image_512': product.image_512 and f'/web/image/product.product/{product.id}/image_512' or '/web/static/src/img/placeholder.png',
                'image_1920': product.image_1920 and f'/web/image/product.product/{product.id}/image_1920' or '/web/static/src/img/placeholder.png',
                'url': product.website_url or f'/shop/product/{product.id}',
                'price': product.lst_price,
            }
            product_data.append(data)

        return {
            'records': product_data,
            'is_sample': with_sample,
        }
