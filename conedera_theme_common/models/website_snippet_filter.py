from odoo import models

class WebsiteSnippetFilter(models.Model):
    _inherit = "website.snippet.filter"

    def _get_brands(self, mode=False):
        Product = self.env['product.template']

        # obtener marcas reales por productos publicados
        brands = Product.search([('website_published', '=', True)]).mapped('brand_id')

        # serializar data para el snippet dynamic
        data = []
        for brand in brands:
            data.append({
                "id": brand.id,
                "name": brand.name,
                "image_512": brand.image_512,
            })

        return {
            "count": len(data),
            "results": data,
        }
