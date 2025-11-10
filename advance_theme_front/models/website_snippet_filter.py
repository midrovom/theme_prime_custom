from odoo import _, api, fields, models
import logging

_logger = logging.getLogger(__name__)

class WebsiteSnippetFilter(models.Model):
    _inherit = 'website.snippet.filter'
    
    def _filter_records_to_values(self, records, is_sample=False):
        res = super()._filter_records_to_values(records, is_sample)

        _logger.info("INGRESA EN FILTER RECORDS ******************************")

        # Aplicar solo cuando el snippet está configurado para categorías
        if self.model_name == 'product.public.category':
            for data in res:
                category = data['_record']

                # Asegurar que tenga URL
                data['url'] = category.website_url

                # Si deseas incluir cantidad de productos dentro de categoría
                data['product_count'] = len(category.product_tmpl_ids)
                
                # Si deseas una imagen por defecto si no tiene
                if not data.get('image_512'):
                    data['image_512'] = "/web/static/img/placeholder.png"

        return res
    

    # def _prepare_values(self, limit=None, search_domain=None):
    #     result = super()._prepare_values(limit=limit, search_domain=search_domain)

    #     _logger.info(f"MOSTRANDO PREPARE VALUES >>>>>>>>>>>>>>>>>>>>>>>>> { result }")