from odoo.addons.theme_prime.controllers.main import ThemePrimeMainClass
from odoo.http import request
from odoo.tools import formatLang

class ThemePrimeMainClassExtended(ThemePrimeMainClass):

    def _prepare_product_data(self, products, fields, pricelist, options=None):
        fields = list(set(fields or []))
        fields += ['attribute_line_ids']
        result = super()._prepare_product_data(products, fields, pricelist, options)

        # Solo aplicar si la compañía del sitio web es la 2
        if request.website.company_id.id == 2:
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

    # Función para mostrar precio tachado
    def _get_computed_product_price(self, product, product_data, price_public_visibility, visibility_label, currency_id):
        res = super()._get_computed_product_price(
            product, product_data, price_public_visibility, visibility_label, currency_id
        )

        # Solo aplicar si la compañía del sitio web es la 2
        if request.website.company_id.id == 2:
            base_price = product.list_price if product._name == 'product.template' else product.product_tmpl_id.list_price
            final_price = product_data.get('price', base_price)
            formatted_price = formatLang(request.env, base_price, currency_obj=currency_id, monetary=True)

            if price_public_visibility and final_price != base_price:
                res.update({
                    'list_price_base_raw': base_price,
                    'list_price_base': formatted_price
                })
            else:
                res.update({
                    'list_price_base_raw': ' ',
                    'list_price_base': ' '
                })

        return res


# from odoo.addons.theme_prime.controllers.main import ThemePrimeMainClass
# from odoo.http import request
# from odoo.tools import formatLang

# class ThemePrimeMainClassExtended(ThemePrimeMainClass):

#     def _prepare_product_data(self, products, fields, pricelist, options=None):
#         fields = list(set(fields or []))
#         fields += ['attribute_line_ids']
#         result = super()._prepare_product_data(products, fields, pricelist, options)

#         for res_product, product in zip(result, products):
#             res_product['attributes'] = []
#             res_product['other_attributes'] = []

#             for line in product.attribute_line_ids:
#                 if line.attribute_id.dr_is_brand:
#                     continue

#                 for val in line.value_ids:
#                     attr_data = {
#                         'id': val.id,
#                         'name': val.name,
#                         'image': val.dr_image and f'/web/image/product.attribute.value/{val.id}/dr_image' or False,
#                         'attribute_name': line.attribute_id.name,
#                     }
#                     if line.attribute_id.attribute_custom:
#                         res_product['attributes'].append(attr_data)
#                     else:
#                         res_product['other_attributes'].append(attr_data)

#         return result

#     #Funcion para mostrar precio tachado

#     def _get_computed_product_price(self, product, product_data, price_public_visibility, visibility_label, currency_id):
#         res = super()._get_computed_product_price(
#             product, product_data, price_public_visibility, visibility_label, currency_id
#         )
#         base_price = product.list_price if product._name == 'product.template' else product.product_tmpl_id.list_price
#         final_price = product_data.get('price', base_price)
#         # formatLang para obtener el valor como string plano
#         formatted_price = formatLang(request.env, base_price, currency_obj=currency_id, monetary=True)
#         # solo mostrar si el precio final es distinto al base
#         if price_public_visibility and final_price != base_price:
#             res.update({
#                 'list_price_base_raw': base_price,
#                 'list_price_base': formatted_price
#             })
#         else:
#             res.update({
#                 'list_price_base_raw': ' ',
#                 'list_price_base': ' '
#             })

#         return res