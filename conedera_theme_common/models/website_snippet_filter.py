from odoo import models, fields, api
from odoo.osv import expression

class WebsiteSnippetFilter(models.Model):
    _inherit = 'website.snippet.filter'

    def _get_products_by_brand(self, website, limit, domain, brand_id, **kwargs):
        """
        Devuelve productos de una marca específica para usar en snippets dinámicos.
        """
        products = self.env['product.product']

        if brand_id:
            # Ajustamos el dominio para incluir la marca seleccionada
            domain = expression.AND([
                domain,
                [('product_tmpl_id.brand_id', '=', brand_id)],
                [('website_published', '=', True)],  
                [('sale_ok', '=', True)],           
            ])

            products = self.env['product.product'].with_context(
                display_default_code=False,
            ).search(domain, limit=limit)

        return products
