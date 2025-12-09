from odoo import api, models
import logging

_logger = logging.getLogger(__name__)

class WebsiteSnippetFilter(models.Model):
    _inherit = 'website.snippet.filter'

    def _filter_records_to_values(self, records, is_sample=False):
        """Corrige el error decode() en campos booleanos"""
        res = super()._filter_records_to_values(records, is_sample)

        # FIX: evitar decode() de valores booleanos del core de Odoo
        for data in res:
            for key, value in list(data.items()):
                if isinstance(value, bool):
                    data[key] = ""  # O "" o convertir a str(value)

        # Custom exclusivo para productos
        if self.model_name in ['product.product', 'product.template']:
            for data in res:
                product = data.get('_record')
                if not product:
                    continue
                
                data['name'] = product.name or ""
                data['brand'] = product.dr_brand_value_id.name if product.dr_brand_value_id else ""

                # Imagen
                if product.image_1920:
                    data['image_1920'] = f"/web/image/{product._name}/{product.id}/image_1920"
                else:
                    data['image_1920'] = "/web/static/img/placeholder.png"

        return res
