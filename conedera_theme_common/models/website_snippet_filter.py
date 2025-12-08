from odoo import api, models
from odoo.osv import expression
from odoo.http import request

class WebsiteSnippetFilter(models.Model):
    _inherit = 'website.snippet.filter'

    def _filter_records_to_values(self, records, is_sample=False):
        res = super()._filter_records_to_values(records, is_sample)

        # Aplicar solo cuando el snippet está configurado para marcas
        if self.model_name == 'product.attribute.value':
            for data in res:
                brand = data['_record']

                # URL para ver productos de esa marca
                data['url'] = "/shop?brand_id=%s" % brand.id

                # Cantidad de productos asociados a esa marca
                product_count = self.env['product.template'].search_count([('dr_brand_value_id', '=', brand.id)])
                data['product_count'] = product_count

                # Imagen por defecto si no tiene
                if not data.get('image_512'):
                    data['image_512'] = "/web/static/img/placeholder.png"

        return res

    @api.model
    def _get_products_by_brand(self, website, limit, domain, **kwargs):
        """Devuelve productos filtrados por marca (dr_brand_value_id)."""
        brand_id = kwargs.get('brand_id')
        products = self.env['product.template']
        if brand_id:
            domain = expression.AND([
                domain,
                [('dr_brand_value_id', '=', int(brand_id))],
            ])
        products = products.with_context(display_default_code=False).search(domain, limit=limit)
        return products


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


