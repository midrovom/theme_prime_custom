from odoo import http
from odoo.http import request

class WebsiteHRRecruitmentCustom(http.Controller):

    @http.route("/my", type="http", auth="user", website=True)
    def portal_home(self, **kwargs):
        applications = request.env['hr.applicant'].sudo().search([
            ('portal_user_id', '=', request.env.user.id)
        ])
        values = {
            'applications': applications,
        }
        return request.render("custom_web_candidatos.portal_home_custom", values)
