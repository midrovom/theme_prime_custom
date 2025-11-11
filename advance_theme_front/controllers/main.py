from odoo.addons.website.controllers.main import Website
from odoo import http, models, fields, _
from odoo.tools import OrderedSet, escape_psql, html_escape as escape, py_to_js_locale
from odoo.http import request, SessionExpiredException
from lxml import etree, html

import requests

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
        domain = [['key', 'ilike', '.dynamic_filter_template_'], ['type', '=', 'qweb']]
        if filter_name:
            domain.append(['key', 'ilike', escape_psql('_%s_' % filter_name)])
        templates = request.env['ir.ui.view'].sudo().search_read(domain, ['key', 'name', 'arch_db'])


        _logger.info(f"MOSTRANDO DOMAIN ************************** { domain }")
        _logger.info(f"MOSTRANDO TEMPLATES ************************** { templates }")

        for t in templates:
            children = etree.fromstring(t.pop('arch_db')).getchildren()
            attribs = children and children[0].attrib or {}
            t['numOfEl'] = attribs.get('data-number-of-elements')
            t['numOfElSm'] = attribs.get('data-number-of-elements-sm')
            t['numOfElFetch'] = attribs.get('data-number-of-elements-fetch')
            t['rowPerSlide'] = attribs.get('data-row-per-slide')
            t['arrowPosition'] = attribs.get('data-arrow-position')
            t['extraClasses'] = attribs.get('data-extra-classes')
            t['columnClasses'] = attribs.get('data-column-classes')
            t['thumb'] = attribs.get('data-thumb')
        return templates
    
    