from odoo import http, _
from odoo.http import request
from odoo.exceptions import UserError, AccessDenied
from markupsafe import Markup
import secrets
import werkzeug
import logging
from werkzeug.urls import url_encode

_logger = logging.getLogger(__name__)

class PortalSignupController(http.Controller):

    @http.route('/web/signup', type='http', auth='public', website=True, sitemap=False)
    def web_auth_signup(self, *args, **kw):
        qcontext = self.get_auth_signup_qcontext()

        if not qcontext.get('token') and not qcontext.get('signup_enabled'):
            raise werkzeug.exceptions.NotFound()

        if 'error' not in qcontext and request.httprequest.method == 'POST':
            try:
                if not request.env['ir.http']._verify_request_recaptcha_token('signup'):
                    raise UserError(_("Suspicious activity detected by Google reCaptcha."))

                # Crear usuario portal con código de verificación
                user = request.env['res.users'].sudo().create({
                    'name': qcontext.get('name'),
                    'login': qcontext.get('login'),
                    'email': qcontext.get('login'),
                    'password': qcontext.get('password'),
                    'groups_id': [(6, 0, [request.env.ref('base.group_portal').id])],
                    'email_verification_code': secrets.token_hex(16),
                    'email_verified': False,
                })

                # Enviar correo con enlace de verificación
                template = request.env.ref('mi_modulo_verificacion_correo.email_verification_template', raise_if_not_found=False)
                if template:
                    template.sudo().send_mail(user.id, force_send=True)

                # Mostrar página de pendiente de verificación
                return request.render('mi_modulo_verificacion_correo.signup_pending')

            except UserError as e:
                qcontext['error'] = e.args[0]
            except Exception as e:
                if request.env["res.users"].sudo().search_count([("login", "=", qcontext.get("login"))], limit=1):
                    qcontext["error"] = _("Another user is already registered using this email address.")
                else:
                    _logger.warning("%s", e)
                    qcontext['error'] = _("Could not create a new account.") + Markup('<br/>') + str(e)

        elif 'signup_email' in qcontext:
            user = request.env['res.users'].sudo().search([('email', '=', qcontext.get('signup_email')), ('state', '!=', 'new')], limit=1)
            if user:
                return request.redirect('/web/login?%s' % url_encode({'login': user.login, 'redirect': '/web'}))

        response = request.render('auth_signup.signup', qcontext)
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        response.headers['Content-Security-Policy'] = "frame-ancestors 'self'"
        return response



def _check_credentials(self, password, user_agent_env):
    super()._check_credentials(password, user_agent_env)
    if self.has_group('base.group_portal') and not self.email_verified:
        raise AccessDenied(_("Debe verificar su correo antes de iniciar sesión."))
