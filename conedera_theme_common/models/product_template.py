from odoo import models

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    def _get_brand_values(self):
        self.ensure_one()
        brand_values = []
        for line in self.attribute_line_ids:
            if line.attribute_id.dr_is_brand:
                for val in line.value_ids:
                    brand_values.append({
                        'id': val.id,
                        'name': val.name,
                    })
        return brand_values
