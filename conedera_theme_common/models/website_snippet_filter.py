from odoo import api, models
import logging

_logger = logging.getLogger(__name__)

class WebsiteSnippetFilter(models.Model):
    _inherit = 'website.snippet.filter'

    def _filter_records_to_values(self, records, is_sample=False):
        # Llamamos al super primero
        res = super()._filter_records_to_values(records, is_sample)

        # FIX: evitar que Odoo intente decode() sobre valores booleanos
        for data in res:
            for key, value in list(data.items()):
                if isinstance(value, bool):   # este fix evita el AttributeError
                    data[key] = ""            # cambiar False/True por string vacío

        # ---- Customización específica para product.template ----
        if self.model_name == 'product.template':
            for data in res:
                product = data.get('_record')

                # Si no hay record, valores por defecto
                if not product:
                    data['name'] = ""
                    data['image_1920'] = "/web/static/img/placeholder.png"
                    data['brand'] = ""
                    continue

                # Imagen del producto
                if not getattr(product, "image_1920", False):
                    data['image_1920'] = "/web/static/img/placeholder.png"
                else:
                    data['image_1920'] = f"/web/image/product.template/{product.id}/image_1920"

                # Nombre del producto
                data['name'] = getattr(product, "name", "") or ""

                # Marca
                brand = getattr(product, "dr_brand_value_id", False)
                data['brand'] = brand.name if brand else ""

                # Asegurar que las claves existan
                data.setdefault('image_1920', "/web/static/img/placeholder.png")
                data.setdefault('name', "")
                data.setdefault('brand', "")

        return res

    @api.model
    def _get_products_by_brand(self, brand_id=None, limit=16):
        # Validación de marca
        if not brand_id or brand_id == 'all':
            _logger.info("No se seleccionó marca, no se retornan productos")
            return []

        try:
            brand_id = int(brand_id)
        except (ValueError, TypeError):
            _logger.error("brand_id inválido: %s", brand_id)
            return []

        # Filtrado de productos por marca
        domain = [
            ('website_published', '=', True),
            ('dr_brand_value_id', '=', brand_id)
        ]
        products = self.env['product.template'].search(domain, limit=limit)

        _logger.info("Filtro por marca: brand_id=%s, productos=%s", brand_id, products.ids)

        dynamic_filter = self.env.context.get('dynamic_filter')
        return dynamic_filter.with_context()._filter_records_to_values(products, is_sample=False)
