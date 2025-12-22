from odoo import _, api, fields, models
from odoo.http import request

import logging

_logger = logging.getLogger(__name__)

class WebsiteSnippetFilter(models.Model):
    _inherit = 'website.snippet.filter'
    
    def _filter_records_to_values(self, records, is_sample=False):
        res = super()._filter_records_to_values(records, is_sample)

        # Aplicar solo cuando el snippet está configurado para categorías
        if self.model_name == 'product.public.category':
            for data in res:
                category = data['_record']

                # Asegurar que tenga URL
                data['url'] = "/shop/category/%s" % request.env['ir.http']._slug(category)

                # Si deseas incluir cantidad de productos dentro de categoría
                data['product_count'] = len(category.product_tmpl_ids)
                
                # Si deseas una imagen por defecto si no tiene
                if not data.get('image_512'):
                    data['image_512'] = "/web/static/img/placeholder.png"

        return res
    

    @api.model
    def _get_public_categories(self, mode=None, **kwargs):
        dynamic_filter = self.env.context.get('dynamic_filter') 
        website = self.env['website'].get_current_website()

        # Dominio base
        domain = [
            ('is_show', '=', True),  # ← tu campo para mostrar/ocultar
            ('website_id', 'in', [False, website.id]),  # Soporte multi-website
        ]

        # Traer categorías ordenadas como en la web
        categories = self.env['product.public.category'].search(domain, order="sequence ASC, name ASC")

        return dynamic_filter.with_context()._filter_records_to_values(categories, is_sample=False)

