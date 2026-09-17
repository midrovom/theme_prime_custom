from odoo import http
from odoo.http import request

class HrEcOnboardingController(http.Controller):

    @http.route('/hr_ec_onboarding/filter_by_date', type='json', auth='user')
    def filter_by_date(self, date_str):
        if date_str:
            start = f"{date_str} 00:00:00"
            end = f"{date_str} 23:59:59"
            domain = [
                ("generated_at", ">=", start),
                ("generated_at", "<=", end),
            ]
        else:
            domain = []
        return domain

