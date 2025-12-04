from odoo.addons.theme_prime.controllers.main import ThemePrimeMainClass
from odoo.http import request
from odoo.tools import formatLang

class ThemePrimeMainClassExtended(ThemePrimeMainClass):

    def _prepare_product_data(self, products, fields, pricelist, options=None):
        fields = list(set(fields or []))
        fields += ['attribute_line_ids']
        result = super()._prepare_product_data(products, fields, pricelist, options)

        for res_product, product in zip(result, products):
            res_product['attributes'] = []
            res_product['other_attributes'] = []

            for line in product.attribute_line_ids:
                if line.attribute_id.dr_is_brand:
                    continue

                for val in line.value_ids:
                    attr_data = {
                        'id': val.id,
                        'name': val.name,
                        'image': val.dr_image and f'/web/image/product.attribute.value/{val.id}/dr_image' or False,
                        'attribute_name': line.attribute_id.name,
                    }
                    if line.attribute_id.attribute_custom:
                        res_product['attributes'].append(attr_data)
                    else:
                        res_product['other_attributes'].append(attr_data)

        return result
