from odoo import models
from odoo.http import request

class ProductTemplate(models.Model):
    _inherit = "product.template"

    def _get_computed_product_price(self, product, product_data, price_public_visibility, visibility_label, currency_id):
        res = super()._get_computed_product_price(
            product, product_data, price_public_visibility, visibility_label, currency_id
        )
        FieldMonetary = request.env['ir.qweb.field.monetary']
        monetary_options = {'display_currency': currency_id}

        base_price = product.product_tmpl_id.list_price
        res.update({
            'list_price_base_raw': base_price if price_public_visibility else ' ',
            'list_price_base': FieldMonetary.value_to_html(base_price, monetary_options) if price_public_visibility else ' '
        })

        return res
