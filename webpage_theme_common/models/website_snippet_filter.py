from odoo import _, api, fields, models
from odoo.http import request

class ProductSnippetHelper:
    # enrich_product_data → Enriquecer productos con URL, marca y una imagen por defecto.
    @staticmethod
    def enrich_product_data(res):
        for data in res:
            product = data['_record']
            data['url'] = product.website_url or "/shop/product/%s" % product.id

            brand_name = ""
            tmpl = product.product_tmpl_id
            for val in tmpl.attribute_line_ids.mapped('value_ids'):
                if val.attribute_id.dr_is_brand:
                    brand_name = val.name
                    break
            data['brand'] = brand_name

            if not data.get('image_512'):
                data['image_512'] = "/web/static/img/placeholder.png"

        return res

class CategorySnippetHelper:
    # enrich_category_data → Enriquecer categorías con URL, cantidad de productos y una imagen por defecto.
    @staticmethod
    def enrich_category_data(res):
        for data in res:
            category = data['_record']
            data['url'] = "/shop/category/%s" % request.env['ir.http']._slug(category)
            data['product_count'] = len(category.product_tmpl_ids)

            if not data.get('image_512'):
                data['image_512'] = "/web/static/img/placeholder.png"

        return res

class WebsiteSnippetFilter(models.Model):
    _inherit = 'website.snippet.filter'

    # _filter_records_to_values → Decide qué helper usar según el modelo (producto o categoría).
    def _filter_records_to_values(self, records, is_sample=False):
        res = super()._filter_records_to_values(records, is_sample)

        if self.model_name == 'product.product':
            res = ProductSnippetHelper.enrich_product_data(res)
        elif self.model_name == 'product.public.category':
            res = CategorySnippetHelper.enrich_category_data(res)

        return res

    # _get_products_by_brand → Devuelve productos filtrados por marca.
    @api.model
    def _get_products_by_brand(self, mode=None, **kwargs):
        dynamic_filter = self.env.context.get('dynamic_filter')
        website = self.env['website'].get_current_website()

        brand_id = kwargs.get("product_brand_id") or self.env.context.get("product_brand_id")

        if not brand_id or brand_id == "all":
            return []

        try:
            brand_id = int(brand_id)
        except Exception:
            return []

        domain = [
            ('website_published', '=', True),
            ('website_id', 'in', [False, website.id]),
            ('attribute_line_ids.value_ids', 'in', [brand_id]),
        ]

        products_tmpl = self.env['product.template'].sudo().search(domain, order="sequence ASC, name ASC")
        products = products_tmpl.mapped('product_variant_ids')

        values = dynamic_filter.with_context()._filter_records_to_values(products, is_sample=False)
        return values

    # _get_public_categories → Devuelve categorías públicas visibles en el sitio web.
    @api.model
    def _get_public_categories(self, mode=None, **kwargs):
        dynamic_filter = self.env.context.get('dynamic_filter')
        website = self.env['website'].get_current_website()

        domain = [
            ('is_show', '=', True),  # campo para mostrar/ocultar
            ('website_id', 'in', [False, website.id]),  # soporte multi-website
        ]

        categories = self.env['product.public.category'].search(domain, order="sequence ASC, name ASC")

        return dynamic_filter.with_context()._filter_records_to_values(categories, is_sample=False)