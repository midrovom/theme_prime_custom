import random
from werkzeug.urls import url_encode
from odoo import http, tools, _
from odoo.addons.auth_signup.models.res_users import SignupError
from odoo.addons.web.controllers.home import ensure_db, Home, SIGN_UP_REQUEST_PARAMS, LOGIN_SUCCESSFUL_PARAMS
from odoo.addons.auth_signup.controllers.main import AuthSignupHome
from odoo.exceptions import UserError
from odoo.http import request
from markupsafe import Markup

class AuthSignupHomeOTP(AuthSignupHome):

    @http.route('/web/signup', type='http', auth='public', website=True, sitemap=False)
    def web_auth_signup(self, *args, **kw):
        qcontext = self.get_auth_signup_qcontext()

        if request.httprequest.method == 'POST' and not qcontext.get('error'):
            try:
                email = qcontext.get('login')

                # Generar código OTP
                code = str(random.randint(100000, 999999))

                # Guardar en sesión
                request.session['signup_data'] = qcontext
                request.session['signup_code'] = code

                # Enviar email
                template = request.env.ref('custom_web_hr_datos_candidatos.email_template_signup_code')
                template.sudo().send_mail(
                    False,
                    force_send=True,
                    email_values={'email_to': email},
                    context={'code': code}
                )

                return request.redirect('/web/signup/verify')

            except Exception as e:
                qcontext['error'] = str(e)

        return request.render('auth_signup.signup', qcontext)
    
    @http.route('/web/signup/verify', type='http', auth='public', website=True)
    def signup_verify(self, **post):
        error = None

        if request.httprequest.method == 'POST':
            user_code = post.get('code')
            real_code = request.session.get('signup_code')

            if user_code == real_code:
                qcontext = request.session.get('signup_data')

                try:
                    # Crear usuario ahora sí
                    self.do_signup(qcontext)

                    # Limpiar sesión
                    request.session.pop('signup_code', None)
                    request.session.pop('signup_data', None)

                    return request.redirect('/web/login?account_created=1')

                except Exception as e:
                    error = str(e)
            else:
                error = "Código incorrecto"

        return request.render('custom_web_hr_datos_candidatos.signup_verify_template', {
            'error': error
        })