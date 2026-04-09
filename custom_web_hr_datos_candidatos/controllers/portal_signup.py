import secrets
from odoo import http, _
from odoo.http import request
from odoo.exceptions import UserError

class AuthSignupHomeCustom(http.Controller):

    @http.route('/web/signup', type='http', auth='public', website=True, sitemap=False)
    def web_auth_signup(self, *args, **kw):
        qcontext = self.get_auth_signup_qcontext()
        if request.httprequest.method == 'POST':
            try:
                # Crear usuario con código
                code = secrets.token_hex(6)
                user = request.env['res.users'].sudo().create({
                    'name': kw.get('name'),
                    'login': kw.get('login'),
                    'password': kw.get('password'),
                    'email_verification_code': code,
                    'email_verified': False,
                    'groups_id': [(6, 0, [request.env.ref('base.group_portal').id])],
                })
                # Enviar correo con el código
                template = request.env.ref('custom_web_hr_datos_candidatos.email_verification_template', raise_if_not_found=False)
                if template:
                    template.sudo().send_mail(user.id, force_send=True)
                # Mostrar pantalla para ingresar el código
                return request.render('custom_web_hr_datos_candidatos.signup_code', {'login': user.login})
            except UserError as e:
                qcontext['error'] = e.args[0]
        return request.render('auth_signup.signup', qcontext)

    @http.route('/web/verify_code', type='http', auth='public', website=True)
    def verify_code(self, **kw):
        login = kw.get('login')
        code_entered = kw.get('verification_code')
        user = request.env['res.users'].sudo().search([('login','=',login)], limit=1)
        if user and user.email_verification_code == code_entered:
            user.sudo().write({'email_verified': True})
            # Autenticar al usuario
            request.session.authenticate(request.db, {'login': login, 'password': user.password})
            return request.redirect('/web')
        return request.render('custom_web_hr_datos_candidatos.signup_invalid')
