from odoo import http
from odoo.http import request
from odoo.addons.website.controllers.main import QueryURL
class WebsiteSaleProducts(http.Controller):

    @http.route(['/website_sale/get_products'], type='json', auth='public', website=True)
    def get_dynamic_snippet_products(self, filter_id=None, limit=None, search_domain=None, with_sample=False):
        """
        Devuelve productos para el snippet dinámico basado en filtros y dominio de búsqueda
        """
        # Dominio base: productos publicados en el sitio web
        domain = [('website_published', '=', True), ('sale_ok', '=', True)]

        # Si hay un dominio adicional lo agregamos
        if search_domain:
            domain += search_domain

        Product = request.env['product.template']

        # Si hay un filtro configurado en website.snippet.filter lo aplicamos
        if filter_id:
            filter_sudo = request.env['website.snippet.filter'].sudo().browse(int(filter_id))
            if filter_sudo.exists():
                domain += filter_sudo._get_eval_domain()

        # Buscar productos con límite
        products = Product.search(domain, limit=limit or 16)

        # Preparar datos para el snippet
        product_data = []
        for product in products:
            data = {
                '_record': product,
                'display_name': product.display_name,
                'price': product.list_price,
                'image_512': product.image_512 and f'/web/image/product.template/{product.id}/image_512' or '/web/static/src/img/placeholder.png',
                'image_1920': product.image_1920 and f'/web/image/product.template/{product.id}/image_1920' or '/web/static/src/img/placeholder.png',
                'url': f'/shop/product/{product.id}',
            }
            product_data.append(data)

        return {
            'records': product_data,
            'is_sample': with_sample,
        }

class WebsiteSaleProductsFilter(http.Controller):
    """Controller para filtros de productos"""

    @http.route(['/website_sale/products_filter'], type='json', auth='public', website=True)
    def get_products_filter(self, filter_name=None):
        """Obtiene o crea un filtro para productos"""
        domain = [
            ('filter_id.model_id', '=', 'product.template'),
            ('filter_id.website_id', 'in', (False, request.website.id)),
        ]

        if filter_name:
            domain += [('filter_id.name', '=', filter_name)]

        filters = request.env['website.snippet.filter'].sudo().search(domain, limit=1)

        if filters:
            return filters.id

        return False


class WebsiteProductSnippet(http.Controller):

    @http.route('/website/snippet/products', type='json', auth='public')
    def products_handler(self, domain=None):
        # Buscar productos publicados y vendibles
        products = request.env['product.template'].sudo().search(
            domain or [('website_published', '=', True), ('sale_ok', '=', True)],
            limit=12
        )

        # Preparar datos para el snippet
        return [{
            "name": prod.name,
            "url": prod.website_url,  # URL amigable del producto
            "price": prod.list_price,  # Precio de venta
            "image": f"/web/image/product.template/{prod.id}/image_1920" if prod.image_1920 else "/web/static/src/img/placeholder.png"
        } for prod in products]
