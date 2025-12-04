from odoo import _, api, fields, models
from odoo.http import request

class WebsiteSnippetFilter(models.Model):
    _inherit = 'website.snippet.filter'

    def _filter_records_to_values(self, records, is_sample=False):
        res = super()._filter_records_to_values(records, is_sample)

        if self.model_name == 'product.brand':
            for data in res:
                brand = data['_record']

                data['url'] = "/shop?brand_id=%s" % brand.id

                data['product_count'] = request.env['product.template'].sudo().search_count([
                    ('brand_id', '=', brand.id),
                    ('website_published', '=', True),
                ])

                if not data.get('image_512'):
                    data['image_512'] = "/web/static/img/placeholder.png"

        return res

    @api.model
    def _get_public_brands(self, mode=None, **kwargs):
        website = self.env['website'].get_current_website()

        domain = [
            ('website_id', 'in', [False, website.id]),
            ('active', '=', True),
        ]

        brands = self.env['product.brand'].search(domain, order="sequence ASC, name ASC")

        return self._filter_records_to_values(brands)
