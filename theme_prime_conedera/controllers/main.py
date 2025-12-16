
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


