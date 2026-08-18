from odoo import http
from odoo.http import request
import logging

_logger = logging.getLogger(__name__)

class WebsiteHRRecruitmentCustom(http.Controller):
    @http.route('/jobs/apply/<model("hr.job"):job>', type="http", auth="user", website=True)
    def quick_apply(self, job, **kwargs):
        try:
            applicant_values = {
                'job_id': job.id,
                'partner_name': request.env.user.name,
                'portal_user_id': request.env.user.id,  
                'email_from': request.env.user.email,
            }

            request.env['hr.applicant'].sudo().create(applicant_values)
            _logger.info(f"Usuario {request.env.user.id} postuló al cargo {job.name}")

        except Exception:
            _logger.exception("Error al registrar postulación rápida")
            return request.redirect('/jobs')

        return request.redirect('/my/applications')


