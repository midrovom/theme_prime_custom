from odoo import models

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    def get_custom_attributes(self):
        """Devuelve los atributos marcados como 'attribute_custom' para este producto"""
        self.ensure_one()
        result = []
        for line in self.attribute_line_ids:
            if line.attribute_id.attribute_custom:
                for val in line.value_ids:
                    result.append({
                        'id': val.id,
                        'name': val.name,
                        'attribute_name': line.attribute_id.name,
                        'image': val.image_1920 and f'/web/image/product.attribute.value/{val.id}/image_1920' or False,
                    })
        return result
