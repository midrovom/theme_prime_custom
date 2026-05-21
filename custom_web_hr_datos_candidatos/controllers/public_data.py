from odoo import http, _
from odoo.http import request
from werkzeug.exceptions import BadRequest
import base64
import json

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

    @http.route('/jobs/recruitment/apply', type='http', auth='public', methods=['POST'], csrf=False)
    def apply_job(self, **kwargs):
        document_lines = []
        for idx, file in enumerate(request.httprequest.files.getlist('curriculumVitae')):
            file_content = base64.b64encode(file.read()).decode('utf-8')
            filename = getattr(file, 'filename', f'documento_{idx+1}.pdf')
            document_lines.append((0, 0, {
                'file': file_content,
                'filename': filename,
            }))

        return request.make_response(
            json.dumps({'status': 'ok', 'files': [d[2]['filename'] for d in document_lines]}),
            headers=[('Content-Type', 'application/json')]
        )


