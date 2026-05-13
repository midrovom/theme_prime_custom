import random
from odoo import http, _
from odoo.addons.auth_signup.controllers.main import AuthSignupHome
from odoo.http import request

class AuthSignupHomeOTP(AuthSignupHome):

    @http.route('/web/signup', type='http', auth='public', website=True, sitemap=False)
    def web_auth_signup(self, *args, **kw):
        qcontext = self.get_auth_signup_qcontext()

        if request.httprequest.method == 'POST' and not qcontext.get('error'):
            try:
                email = qcontext.get('login')

                # Validar que no exista ya un usuario con ese correo
                existing_user = request.env['res.users'].sudo().search([('login', '=', email)], limit=1)
                if existing_user:
                    qcontext['error'] = "Ya existe una cuenta asociada a este correo."
                    return request.render('auth_signup.signup', qcontext)

                # Generar código OTP
                code = str(random.randint(100000, 999999))

                # Guardar en sesión
                request.session['signup_data'] = qcontext
                request.session['signup_code'] = code

                # Buscar el servidor de correo marcado como reclutamiento
                mail_server = request.env['ir.mail_server'].sudo().search([('is_recruitment_server', '=', True)], limit=1)
                if not mail_server:
                    raise Exception("No se ha configurado un servidor de correo de reclutamiento.")

                smtp_user = mail_server.smtp_user

                # Enviar correo directamente con el código
                mail_values = {
                    'subject': 'Código de verificación',
                    'body_html': f'<p>Tu código de verificación es:</p><h2>{code}</h2>',
                    'email_to': email,
                    'email_from': smtp_user,
                }
                mail = request.env['mail.mail'].sudo().create(mail_values)
                mail.sudo().send()

                return request.redirect('/web/signup/verify')

            except Exception as e:
                qcontext['error'] = str(e)

        return request.render('auth_signup.signup', qcontext)
    
    @http.route('/web/signup', type='http', auth='public', website=True, sitemap=False)
    def web_auth_signup(self, *args, **kw):
        qcontext = self.get_auth_signup_qcontext()

        if request.httprequest.method == 'POST' and not qcontext.get('error'):
            try:
                # Validar términos y condiciones
                accept_terms = kw.get('accept_terms')
                if not accept_terms:
                    qcontext['error'] = "Debe aceptar los términos y condiciones para registrarse."
                    return request.render('auth_signup.signup', qcontext)

                email = qcontext.get('login')

                # Validar que no exista ya un usuario con ese correo
                existing_user = request.env['res.users'].sudo().search([('login', '=', email)], limit=1)
                if existing_user:
                    qcontext['error'] = "Ya existe una cuenta asociada a este correo."
                    return request.render('auth_signup.signup', qcontext)

                # Generar código OTP
                code = str(random.randint(100000, 999999))

                # Guardar en sesión
                request.session['signup_data'] = qcontext
                request.session['signup_code'] = code

                # Buscar servidor de correo
                mail_server = request.env['ir.mail_server'].sudo().search([('is_recruitment_server', '=', True)], limit=1)
                if not mail_server:
                    raise Exception("No se ha configurado un servidor de correo de reclutamiento.")

                smtp_user = mail_server.smtp_user

                # Enviar correo con el código
                mail_values = {
                    'subject': 'Código de verificación',
                    'body_html': f'<p>Tu código de verificación es:</p><h2>{code}</h2>',
                    'email_to': email,
                    'email_from': smtp_user,
                }
                mail = request.env['mail.mail'].sudo().create(mail_values)
                mail.sudo().send()

                return request.redirect('/web/signup/verify')

            except Exception as e:
                qcontext['error'] = str(e)

        return request.render('auth_signup.signup', qcontext)
