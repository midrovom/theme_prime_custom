from odoo import http
from odoo.http import request

class CustomRedirect(http.Controller):

    @http.route('/', type='http', auth="public", website=True)
    def redirect_to_login(self, **kwargs):
        return request.redirect('/web/login')
