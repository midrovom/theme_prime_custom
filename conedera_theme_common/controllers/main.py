from odoo.addons.website_sale.controllers.main import WebsiteSale
from odoo.http import request

class WebsiteSaleExtended(WebsiteSale):

    def _get_product_attributes(self, product):
        """Devuelve atributos separados en custom y otros"""
        attributes = []
        other_attributes = []

        for line in product.attribute_line_ids:
            if getattr(line.attribute_id, 'dr_is_brand', False):
                continue

            for val in line.value_ids:
                attr_data = {
                    'id': val.id,
                    'name': val.name,
                    'image': val.dr_image and f'/web/image/product.attribute.value/{val.id}/dr_image' or False,
                    'attribute_name': line.attribute_id.name,
                }
                if line.attribute_id.attribute_custom:
                    attributes.append(attr_data)
                else:
                    other_attributes.append(attr_data)

        return {'attributes': attributes, 'other_attributes': other_attributes}

    def _prepare_product_values(self, product, category=None):
        """Sobreescribe el método que arma el diccionario para la vista"""
        values = super()._prepare_product_values(product, category)
        values.update(self._get_product_attributes(product))
        return values
