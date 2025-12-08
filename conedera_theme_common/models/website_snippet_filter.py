from odoo import api, models
from odoo.osv import expression
import logging

_logger = logging.getLogger(__name__)

class WebsiteSnippetFilter(models.Model):
    _inherit = 'website.snippet.filter'

    def _filter_records_to_values(self, records, is_sample=False):
        res = super()._filter_records_to_values(records, is_sample)

        if self.model_name == 'product.template':
            for data in res:
                product = data.get('_record')

                # Validación: si no hay record, continuar
                if not product:
                    data['name'] = ""
                    data['image_1920'] = "/web/static/img/placeholder.png"
                    data['brand'] = ""
                    continue

                # Imagen del producto (usa image_1920 o placeholder)
                if not getattr(product, "image_1920", False):
                    data['image_1920'] = "/web/static/img/placeholder.png"
                else:
                    data['image_1920'] = "/web/image/product.template/%s/image_1920" % product.id

                # Nombre del producto (siempre string)
                data['name'] = getattr(product, "name", "") or ""

                # Marca (siempre string)
                brand = getattr(product, "dr_brand_value_id", False)
                data['brand'] = brand.name if brand else ""

                # Validación extra: asegurar que las claves existen
                if 'image_1920' not in data:
                    data['image_1920'] = "/web/static/img/placeholder.png"
                if 'name' not in data:
                    data['name'] = ""
                if 'brand' not in data:
                    data['brand'] = ""

        return res

    @api.model
    def _get_products_by_brand(self, brand_id=None, limit=16):
        # Validación: si no se selecciona marca, no devolver nada
        if not brand_id or brand_id == 'all':
            _logger.info("No se seleccionó marca, no se retornan productos")
            return []

        try:
            brand_id = int(brand_id)
        except (ValueError, TypeError):
            _logger.error("brand_id inválido: %s", brand_id)
            return []

        # Si hay marca seleccionada, filtrar por ella
        domain = [
            ('website_published', '=', True),
            ('dr_brand_value_id', '=', brand_id)
        ]
        products = self.env['product.template'].search(domain, limit=limit)

        _logger.info("Filtro por marca: brand_id=%s, productos encontrados=%s", brand_id, products.ids)

        dynamic_filter = self.env.context.get('dynamic_filter')
        return dynamic_filter.with_context()._filter_records_to_values(products, is_sample=False)

    # @api.model
    # def _get_products_by_brand(self, website, limit, domain, **kwargs):
    #     """Devuelve productos filtrados por marca (dr_brand_value_id)."""
    #     brand_id = kwargs.get('brand_id')
    #     products = self.env['product.template']
    #     if brand_id:
    #         domain = expression.AND([
    #             domain,
    #             [('dr_brand_value_id', '=', int(brand_id))],
    #         ])
    #     products = products.with_context(display_default_code=False).search(domain, limit=limit)
    #     return products


