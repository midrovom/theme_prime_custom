from odoo import api, models, request
import logging

_logger = logging.getLogger(__name__)


class WebsiteSnippetFilter(models.Model):
    _inherit = 'website.snippet.filter'

    def _get_records(self):
        """
        Website builder NO ejecuta el server action.
        Por eso, forzamos que cuando estemos en modo builder
        el snippet cargue productos reales filtrados por marca.
        """
        try:
            is_builder = request and "edit" in request.httprequest.url
        except Exception:
            is_builder = False

        if is_builder and self.model_name == "product.template":
            brand_id = request.params.get("productBrandId")

            _logger.info("BUILDER → cargando productos reales para brand_id=%s", brand_id)

            return self._get_products_by_brand(brand_id)
        
        return super()._get_records()

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

        dynamic_filter = self.env['website.snippet.filter']
        return dynamic_filter._filter_records_to_values(products, is_sample=False)

    def _filter_records_to_values(self, records, is_sample=False):
        try:
            is_builder = request and "edit" in request.httprequest.url
        except Exception:
            is_builder = False

        if is_builder:
            is_sample = False

        # Super
        res = super()._filter_records_to_values(records, is_sample)

        # Fix de booleans
        for data in res:
            for key, value in list(data.items()):
                if isinstance(value, bool):
                    data[key] = ""

        # Custom para productos
        if self.model_name == "product.template":
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
