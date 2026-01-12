from odoo.addons.theme_prime.controllers.main import ThemePrimeMainClass
from odoo.addons.website_sale.controllers.main import WebsiteSale
from odoo.http import request
from odoo.tools import formatLang
from odoo import http

# class ThemePrimeMainClassExtended(ThemePrimeMainClass):

#     def _prepare_product_data(self, products, fields, pricelist, options=None):
#         fields = list(set(fields or []))
#         fields += ['attribute_line_ids']
#         result = super()._prepare_product_data(products, fields, pricelist, options)

#         # Aplicar siempre, sin importar la compañía
#         for res_product, product in zip(result, products):
#             res_product['attributes'] = []
#             res_product['other_attributes'] = []

#             for line in product.attribute_line_ids:
#                 # Saltar si es marca
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

class ThemePrimeMainClassExtended(ThemePrimeMainClass):

    def _prepare_product_data(self, products, fields, pricelist, options=None):
        fields = list(set(fields or []))
        fields += ['attribute_line_ids']
        result = super()._prepare_product_data(products, fields, pricelist, options)

        # Solo aplicar si la compañía del sitio web es la 1
        if request.website.company_id.id == 1:
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
        base_price = product.list_price if product._name == 'product.template' else product.product_tmpl_id.list_price
        final_price = product_data.get('price', base_price)
        # formatLang para obtener el valor como string plano
        formatted_price = formatLang(request.env, base_price, currency_obj=currency_id, monetary=True)
        # solo mostrar si el precio final es distinto al base
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

#conedera
class ThemePrimeMainClassExtendeds(ThemePrimeMainClass):
    # Funcion para filtrar productos por marca
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
    
# Funcion para agregar los atributos marcados al filtro
class WebsiteSaleExtended(WebsiteSale):

    @http.route()
    def shop(self, page=0, category=None, search='', min_price=0.0,
             max_price=0.0, ppg=False, **post):

        response = super().shop(
            page=page,
            category=category,
            search=search,
            min_price=min_price,
            max_price=max_price,
            ppg=ppg,
            **post
        )

        attributes = response.qcontext.get('attributes')
        if attributes:
            attributes.read(['filter_attribute'])
            response.qcontext['attributes'] = attributes.filtered(
                lambda a: a.filter_attribute
            )

        return response
