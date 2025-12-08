
from odoo import api, models
from odoo.osv import expression
from odoo.http import request
import logging

_logger = logging.getLogger(__name__)

class WebsiteSnippetFilter(models.Model):
    _inherit = 'website.snippet.filter'

    def _filter_records_to_values(self, records, is_sample=False):
        # Llamamos al super para obtener la estructura base
        res = super()._filter_records_to_values(records, is_sample)

        # Aplicar solo cuando el snippet está configurado para productos
        if self.model_name == 'product.template':
            for data in res:
                product = data['_record']

                # URL del producto
                data['url'] = "/shop/product/%s" % product.id

                # Imagen por defecto si no tiene
                if not data.get('image_512'):
                    data['image_512'] = "/web/static/img/placeholder.png"

                # Puedes añadir más campos si lo necesitas
                data['description_sale'] = product.description_sale or ""

        return res

    @api.model
    def _get_products_by_brand(self, website, limit, domain, **kwargs):
        brand_id = kwargs.get('brand_id')
        products = self.env['product.template']
        if brand_id and brand_id != 'all':
            domain = expression.AND([
                domain,
                [('dr_brand_value_id', '=', int(brand_id))],
            ])
        products = products.with_context(display_default_code=False).search(domain, limit=limit)

        # Log para depuración
        _logger.info("Filtro por marca: brand_id=%s, productos encontrados=%s", brand_id, products.ids)

        # Igual que en categorías: devolvemos los valores procesados
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


