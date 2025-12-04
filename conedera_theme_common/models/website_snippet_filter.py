from odoo import _, api, fields, models
from odoo.osv import expression

class WebsiteProductSnippet(models.Model):
    _inherit = 'website.snippet.filter'

    @api.model
    def _get_products_custom(self, limit=20, **kwargs):
        website = self.env['website'].get_current_website()

        # Dominio: solo productos publicados en el sitio web actual
        domain = expression.AND([
            [('website_published', '=', True)],
            website.website_domain(),
            [('company_id', 'in', [False, website.company_id.id])],
        ])

        # Buscar productos
        products = self.env['product.product'].search(domain, limit=limit)
        return self._filter_records_to_values(products, is_sample=False)
