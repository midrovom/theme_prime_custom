from odoo import api, models
import logging

_logger = logging.getLogger(__name__)


class WebsiteSnippetFilter(models.Model):
    _inherit = 'website.snippet.filter'

    def _filter_records_to_values(self, records, is_sample=False):
        brand_ctx = self.env.context.get("product_brand_id")
        is_builder = bool(brand_ctx)
        if is_builder and self.model_name == "product.template":
            is_sample = False

            # Si viene marca → filtrar productos reales
            if brand_ctx and brand_ctx != "all":
                try:
                    brand_id = int(brand_ctx)
                except Exception:
                    brand_id = False

                if brand_id:
                    records = self.env['product.template'].search([
                        ('website_published', '=', True),
                        ('dr_brand_value_id', '=', brand_id)
                    ])

        # Llamada normal al super
        res = super()._filter_records_to_values(records, is_sample)

        # FIX: evitar decode() de valores booleanos
        for data in res:
            for key, value in list(data.items()):
                if isinstance(value, bool):
                    data[key] = ""

        # Custom de product.template
        if self.model_name == 'product.template':
            for data in res:
                product = data.get('_record')

                if not product:
                    data['name'] = ""
                    data['image_1920'] = "/web/static/img/placeholder.png"
                    data['brand'] = ""
                    continue

                data['name'] = product.name or ""
                data['brand'] = product.dr_brand_value_id.name if product.dr_brand_value_id else ""

                # Imagen
                if product.image_1920:
                    data['image_1920'] = f"/web/image/product.template/{product.id}/image_1920"
                else:
                    data['image_1920'] = "/web/static/img/placeholder.png"

        return res

    @api.model
    def _get_products_by_brand(self, brand_id=None, limit=16):
        # Leer marca desde contexto si no viene por parámetro
        if not brand_id:
            brand_id = self.env.context.get("product_brand_id")

        if not brand_id or brand_id == 'all':
            _logger.info("No se seleccionó marca, no se retornan productos")
            return []

        try:
            brand_id = int(brand_id)
        except (ValueError, TypeError):
            _logger.error("brand_id inválido: %s", brand_id)
            return []

        domain = [
            ('website_published', '=', True),
            ('dr_brand_value_id', '=', brand_id)
        ]
        products = self.env['product.template'].search(domain, limit=limit)

        _logger.info("Filtro por marca: brand_id=%s, productos=%s", brand_id, products.ids)

        return self._filter_records_to_values(products, is_sample=False)
