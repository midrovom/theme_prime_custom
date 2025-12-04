
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
                        res_product['brands'].append({
                            'id': val.id,
                            'name': val.name,
                            'color': getattr(val, 'html_color', False) or getattr(val, 'dr_color', False),
                        })

        return result

# class ThemePrimeMainClassExtended(ThemePrimeMainClass):

#     def _prepare_product_data(self, products, fields, pricelist, options=None):
#         fields = list(set(fields or []))
#         fields += ['attribute_line_ids']
#         result = super()._prepare_product_data(products, fields, pricelist, options)

#         for res_product, product in zip(result, products):
#             # Inicializamos la lista de marcas
#             res_product['brands'] = []

#             for line in product.attribute_line_ids:
#                 # Solo tomamos los atributos que tengan el check dr_is_brand
#                 if line.attribute_id.dr_is_brand:
#                     for val in line.value_ids:
#                         # Guardamos únicamente el campo name
#                         res_product['brands'].append(val.name)

#         return result
