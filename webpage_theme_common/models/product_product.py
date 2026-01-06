from odoo import models

class ProductProduct(models.Model):
    _inherit = 'product.product'

    def _get_other_attributes(self):
        self.ensure_one()
        result = []
        for pav in self.product_template_attribute_value_ids:
            attribute = pav.attribute_id
            if not attribute.dr_is_brand and not attribute.attribute_custom:
                result.append(pav.name)
        return result
