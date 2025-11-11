from addons.website.controllers.main import Website
from odoo import http, models, fields, _

import logging


_logger = logging.getLogger(__name__)

class WebsiteCustom(Website):

    @http.route('/website/snippet/filters', type='json', auth='public', website=True, readonly=True)
    def get_dynamic_filter(self, filter_id, template_key, limit=None, search_domain=None, with_sample=False, **custom_template_data):
        _logger.info("ENTRA EN GET DYNAMIC FILTER ******************************")
        
        res = super().get_dynamic_filter(filter_id, template_key, limit=limit, search_domain=search_domain, with_sample=with_sample, **custom_template_data)

        _logger.info(f"MOSTRANDO RES ************************************** { res }")
        
        return res

    @http.route('/website/snippet/filter_templates', type='json', auth='public', website=True, readonly=True)
    def get_dynamic_snippet_templates(self, filter_name=False):
        _logger.info("ENTRA EN GET DYNAMIC SNIPPET TEMPLATES ******************************")
        
        res = super().get_dynamic_snippet_templates(filter_name=filter_name)

        _logger.info(f"MOSTRANDO RES ************************************** { res }")

        return res