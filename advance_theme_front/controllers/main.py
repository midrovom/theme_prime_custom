from odoo.addons.website.controllers.main import Website
from odoo import http, models, fields, _

import logging


_logger = logging.getLogger(__name__)

class WebsiteCustom(Website):

    @http.route('/website/snippet/filter_templates', type='json', auth='public', website=True, readonly=True)
    def get_dynamic_snippet_templates(self, filter_name=False):
        _logger.info("ENTRA EN GET DYNAMIC SNIPPET TEMPLATES ******************************")
        
        res = super().get_dynamic_snippet_templates(filter_name=filter_name)

        _logger.info(f"MOSTRANDO RES ************************************** { res }")

        return res