from odoo import api, models
import logging

_logger = logging.getLogger(__name__)

class WebsiteSnippetFilter(models.Model):
    _inherit = 'website.snippet.filter'

    def _filter_records_to_values(self, records, is_sample=False):
        # SUPER
        res = super()._filter_records_to_values(records, is_sample)

        # FIX: evitar errores con booleanos
        for data in res:
            for key, value in list(data.items()):
                if isinstance(value, bool):
                    data[key] = ""

        # Personalización para productos
        if self.model_name == 'product.template':
            for data in res:
                product = data.get('_record')

                if not product:
                    data['name'] = ""
                    data['image_1920'] = "/web/static/img/placeholder.png"
                    data['brand'] = ""
                    continue

                # Imagen
                if not getattr(product, "image_1920", False):
                    data['image_1920'] = "/web/static/img/placeholder.png"
                else:
                    data['image_1920'] = (
                        f"/web/image/product.template/{product.id}/image_1920"
                    )

                # Nombre
                data['name'] = getattr(product, "name", "") or ""

                # Marca
                brand = getattr(product, "dr_brand_value_id", False)
                data['brand'] = brand.name if brand else ""

                data.setdefault('image_1920', "/web/static/img/placeholder.png")
                data.setdefault('name', "")
                data.setdefault('brand', "")

        return res

    @api.model
    def _get_products_by_brand(self, brand_id=None, limit=16):

        if not brand_id or brand_id == "all":
            return []

        try:
            brand_id = int(brand_id)
        except Exception:
            _logger.error("Brand ID inválido: %s", brand_id)
            return []

        domain = [
            ('website_published', '=', True),
            ('dr_brand_value_id', '=', brand_id),
        ]

        products = self.env['product.template'].search(domain, limit=limit)

        _logger.info("Filtrando productos: brand=%s productos=%s", brand_id, products.ids)

        dynamic_filter = self.env.context.get('dynamic_filter')
        return dynamic_filter.with_context()._filter_records_to_values(products, is_sample=False)
