from odoo import api, models
from odoo.http import request
from collections import defaultdict

class WebsiteSnippetFilterBrand(models.Model):
    _inherit = 'website.snippet.filter'

    def _filter_records_to_values(self, records, is_sample=False):
        res = super()._filter_records_to_values(records, is_sample)

        # Solo aplicar si el modelo es product.attribute.value (marcas)
        if self.model_name == 'product.attribute.value':
            for data in res:
                brand = data['_record']

                # URL de la marca en la tienda
                data['url'] = f"/shop?brand_id={brand.id}"

                # Fallback si no existe imagen
                if not data.get("image_512"):
                    data["image_512"] = "/web/static/img/placeholder.png"

        return res

    @api.model
    def _get_public_brands(self, mode=None, **kwargs):
        """
        Retorna solo valores de atributos cuyo attribute_id.name = 'Brand'
        """
        PAV = self.env['product.attribute.value']

        brands = PAV.search([
            ('attribute_id.name', '=', 'Brand'),
            ('active', '=', True)
        ], order="name ASC")

        return self._filter_records_to_values(brands, is_sample=False)
