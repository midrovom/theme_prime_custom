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
                product = data['_record']

                # Imagen del producto (usa la imagen del template)
                if not data.get('image_512'):
                    data['image_512'] = "/web/static/img/placeholder.png"

                # Nombre del producto
                data['name'] = product.name or ""

                # Marca (campo dr_brand_value_id)
                # Aseguramos que siempre exista la clave 'brand'
                data['brand'] = product.dr_brand_value_id.name if product.dr_brand_value_id else ""

        return res

    @api.model
    def _get_products_by_brand(self, brand_id=None, limit=16):
        domain = [('website_published', '=', True)]
        if brand_id and brand_id != 'all':
            domain = expression.AND([
                domain,
                [('dr_brand_value_id', '=', int(brand_id))],
            ])
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


