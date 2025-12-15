from odoo.addons.website_sale.controllers.main import WebsiteSale

class WebsiteSaleExtended(WebsiteSale):

    def _prepare_product_data(self, products, fields, pricelist, options=None):
        fields = list(set(fields or []))
        fields += ['attribute_line_ids']
        result = super()._prepare_product_data(products, fields, pricelist, options)

        for res_product, product in zip(result, products):
            res_product['attributes'] = []
            for line in product.attribute_line_ids:
                if line.attribute_id.attribute_custom:
                    for val in line.value_ids:
                        res_product['attributes'].append({
                            'id': val.id,
                            'name': val.name,
                            'attribute_name': line.attribute_id.name,
                            'image': val.image_1920 and f'/web/image/product.attribute.value/{val.id}/image_1920' or False,
                        })
        return result
