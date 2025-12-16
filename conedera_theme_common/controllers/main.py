from odoo.addons.website_sale.controllers.main import WebsiteSale
from odoo.osv import expression


class WebsiteSaleFilterAttribute(WebsiteSale):

    def _get_search_domain(self, search, category, attrib_values):
        domain = super()._get_search_domain(search, category, attrib_values)

        allowed_attributes = self.env['product.attribute'].search([
            ('filter_attribute', '=', True)
        ])

        domain = expression.AND([
            domain,
            [('attribute_line_ids.attribute_id', 'in', allowed_attributes.ids)]
        ])

        return domain
