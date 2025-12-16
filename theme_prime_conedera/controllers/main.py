
from odoo.addons.theme_prime.controllers.main import ThemePrimeMainClass
class ThemePrimeMainClassExtended(ThemePrimeMainClass):

    def _prepare_product_data(self, products, fields, pricelist, options=None):
        fields = list(set(fields or []))
        fields += ['attribute_line_ids']
        result = super()._prepare_product_data(products, fields, pricelist, options)

        for res_product, product in zip(result, products):
            res_product['brands'] = []

            for line in product.attribute_line_ids:
                if line.attribute_id.dr_is_brand:
                    for val in line.value_ids:
                        res_product['brands'].append(val.name)

        return result
    
# Funcion para filtrar atributos marcados
    def _get_shop_values(self, category, search, **kwargs):
        values = super()._get_shop_values(category, search, **kwargs)

        attributes = values.get('attributes')
        if attributes:
            values['attributes'] = attributes.filtered(
                lambda a: a.filter_attribute
            )

        return values
