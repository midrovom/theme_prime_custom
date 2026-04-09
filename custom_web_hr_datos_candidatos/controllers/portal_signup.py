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
                # Validar código ingresado
                code_entered = kw.get('verification_code')
                user = request.env['res.users'].sudo().search([('login', '=', qcontext.get('login'))], limit=1)

                if not user:
                    # Si no existe, primero generamos y enviamos el código
                    code = secrets.token_hex(6)
                    user = request.env['res.users'].sudo().create({
                        'name': qcontext.get('name'),
                        'login': qcontext.get('login'),
                        'email': qcontext.get('login'),
                        'password': qcontext.get('password'),
                        'groups_id': [(6, 0, [request.env.ref('base.group_portal').id])],
                        'email_verification_code': code,
                        'email_verified': False,
                    })
                    template = request.env.ref('custom_web_hr_datos_candidatos.email_verification_template', raise_if_not_found=False)
                    if template:
                        template.sudo().send_mail(user.id, force_send=True)
                    qcontext['error'] = _("Se ha enviado un código de verificación a su correo. Ingréselo en el campo correspondiente.")
                    return request.render('auth_signup.signup', qcontext)

                else:
                    # Si ya existe, validar el código
                    if user.email_verification_code != code_entered:
                        qcontext['error'] = _("El código de verificación no es válido.")
                        return request.render('auth_signup.signup', qcontext)

                    # Código correcto → marcar verificado y permitir login
                    user.sudo().write({'email_verified': True})
                    return self.web_login(*args, **kw)

            except UserError as e:
                qcontext['error'] = e.args[0]

        response = request.render('auth_signup.signup', qcontext)
        return response