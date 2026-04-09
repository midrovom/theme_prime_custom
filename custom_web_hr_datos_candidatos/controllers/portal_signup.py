
import secrets
from odoo import http, _
from odoo.http import request
from odoo.exceptions import UserError

class AuthSignupHomeCustom(http.Controller):

    @http.route('/web/signup', type='http', auth='public', website=True, sitemap=False)
    def web_auth_signup(self, *args, **kw):
        qcontext = self.get_auth_signup_qcontext()

        if not qcontext.get('token') and not qcontext.get('signup_enabled'):
            raise werkzeug.exceptions.NotFound()

        if 'error' not in qcontext and request.httprequest.method == 'POST':
            try:
                self.do_signup(qcontext)

                # Buscar el usuario recién creado
                user = request.env['res.users'].sudo().search([('login', '=', qcontext.get('login'))], limit=1)
                if user and user.has_group('base.group_portal'):
                    user.write({
                        'email_verification_code': secrets.token_hex(16),
                        'email_verified': False,
                    })
                    template = request.env.ref('custom_web_hr_datos_candidatos.email_verification_template', raise_if_not_found=False)
                    if template:
                        template.sudo().send_mail(user.id, force_send=True)
                    return request.render('custom_web_hr_datos_candidatos.signup_pending')

                return self.web_login(*args, **kw)

            except UserError as e:
                qcontext['error'] = e.args[0]

        response = request.render('auth_signup.signup', qcontext)
        return response

class VerifyEmailController(http.Controller):

    @http.route('/web/verify_email', type='http', auth='public', website=True)
    def verify_email(self, token=None, **kwargs):
        user = request.env['res.users'].sudo().search([('email_verification_code','=',token)], limit=1)
        if user and user.has_group('base.group_portal'):
            user.sudo().write({'email_verified': True})
            return request.render('custom_web_hr_datos_candidatos.signup_success')
        return request.render('custom_web_hr_datos_candidatos.signup_invalid')
