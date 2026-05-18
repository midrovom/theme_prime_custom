from odoo import http, _
from odoo.http import request
from werkzeug.exceptions import BadRequest

from odoo.addons.http_routing.models.ir_http import slugify


import logging
import json

_logger = logging.getLogger(__name__)

class PublicDataController(http.Controller):

    @http.route('/api/countries', auth='public', type='http', methods=['GET'])
    def get_countries(self):
        countries = request.env['res.country'].sudo().search_read([], ['id', 'name'])
        return http.Response(json.dumps(countries), content_type='application/json')
    
    @http.route('/api/study_levels', auth='public', type='http', methods=['GET'])
    def get_study_levels(self):
        study_levels = request.env['hr.recruitment.degree'].sudo().search_read([], ['id', 'name'])
        return http.Response(json.dumps(study_levels), content_type='application/json')
    
    @http.route('/api/states/<int:country_id>', auth='public', type='http', methods=['GET'])
    def get_states(self, country_id):
        states = request.env['res.country.state'].sudo().search_read(
            [('country_id', '=', country_id)],
            ['id', 'name']
        )
        return http.Response(json.dumps(states), content_type='application/json')
    

class RecruitmentController(http.Controller):

    @http.route('/jobs/recruitment/<string:job_slug>', type='http', auth="public", website=True)
    def recruitment_form(self, job_slug, **kwargs):
        if not request.session.uid:
            return request.redirect('/web/login?redirect=/jobs/recruitment/%s' % job_slug)

        job_name = job_slug.replace('-', ' ')
        job = request.env['hr.job'].sudo().search([('name', '=', job_name)], limit=1)
        if not job:
            return request.not_found()

        return request.render('custom_web_hr_datos_candidatos.web_recruitment', {
            'job': job,
            'job_slug': job_slug
        })

