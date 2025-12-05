from odoo import models, api, fields

class WebsiteSnippetFilter(models.Model):
    _inherit = "website.snippet.filter"

    def _get_products_by_brand(self, website, limit, domain, brand_id=None, **kwargs):
        Product = self.env['product.product']
        AttributeValue = self.env['product.attribute.value']

        brand = AttributeValue.browse(
            brand_id and int(brand_id)
        ).exists()

        if not brand:
            return Product

        # Productos donde la marca está en attribute_value_ids
        domain = [
            ('website_published', '=', True),
            ('attribute_value_ids', 'in', [brand.id])
        ]

        products = Product.with_context(
            display_default_code=False
        ).search(domain, limit=limit)

        return products

    def _get_all_brands(self, website, limit, domain, **kwargs):
        AttributeValue = self.env['product.attribute.value']

        brands = AttributeValue.search([
            ('attribute_id', '=', self.env.ref('website_sale.product_attribute_brand').id),
        ])

        return brands
