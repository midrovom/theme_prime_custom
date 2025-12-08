from odoo import api, models, request
import logging

_logger = logging.getLogger(__name__)

class WebsiteSnippetFilter(models.Model):
    _inherit = 'website.snippet.filter'

    def _get_records(self):
        """
        Odoo 18 no llama al server action dentro del builder,
        por lo que debemos interceptar la carga y devolver productos reales.
        """
        try:
            req = request.httprequest
            is_builder = req and "edit" in req.url
        except Exception:
            is_builder = False

        if is_builder and self.model_name == "product.template":
            brand_id = request.params.get("productBrandId")
            if brand_id:
                _logger.info("Website Builder → cargando productos por marca %s", brand_id)
                return self._get_products_by_brand(brand_id)

        # Caso normal (frontend o sin marca)
        return super()._get_records()

    def _filter_records_to_values(self, records, is_sample=False):

        # Forzar datos reales en el builder
        try:
            req = request.httprequest
            is_builder = req and "edit" in req.url
        except Exception:
            is_builder = False

        if is_builder and self.model_name == "product.template":
            is_sample = False

        # Llamada al super
        res = super()._filter_records_to_values(records, is_sample)

        # FIX: Odoo trata booleans como bytes → error decode()
        for data in res:
            for key, value in list(data.items()):
                if isinstance(value, bool):
                    data[key] = ""

        # Custom para product.template
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

                if product.image_1920:
                    data['image_1920'] = f"/web/image/product.template/{product.id}/image_1920"
                else:
                    data['image_1920'] = "/web/static/img/placeholder.png"

        return res

    @api.model
    def _get_products_by_brand(self, brand_id=None, limit=16):

        if not brand_id or brand_id == 'all':
            return []

        try:
            brand_id = int(brand_id)
        except Exception:
            return []

        domain = [
            ('website_published', '=', True),
            ('dr_brand_value_id', '=', brand_id)
        ]

        products = self.env['product.template'].search(domain, limit=limit)

        _logger.info("Filtro por marca %s → productos %s", brand_id, products.ids)

        # NO usar dynamic_filter, causa errores en builder
        return self._filter_records_to_values(products, is_sample=False)
