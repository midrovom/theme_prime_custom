from odoo import api, models
from odoo.osv import expression
import logging

_logger = logging.getLogger(__name__)

class WebsiteSnippetFilter(models.Model):
    _inherit = 'website.snippet.filter'

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

        return products   # devolvemos el recordset


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


