from odoo import http
from odoo.http import request

class WebsiteHRRecruitmentCustom(http.Controller):

    @http.route("/my/applications", type="http", auth="user", website=True)
    def my_applications(self, **kwargs):
        applications = request.env['hr.applicant'].sudo().search([
            ('portal_user_id', '=', request.env.user.id)
        ])
        values = {
            'applications': applications,
        }
        return request.render("custom_web_candidatos.portal_my_applications", values)

    @http.route("/jobs/continue/<int:applicant_id>", type="http", auth="user", website=True)
    def continue_application(self, applicant_id, **kwargs):
        applicant = request.env['hr.applicant'].sudo().browse(applicant_id)
        if not applicant.exists() or applicant.portal_user_id.id != request.env.user.id:
            return request.not_found()
        return request.render("custom_web_candidatos.portal_continue_application", {
            'applicant': applicant,
        })
