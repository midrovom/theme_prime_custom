# -*- coding: utf-8 -*-
"""Gestión de credenciales del usuario autenticado, sin modificar otros usuarios."""
import logging
import re
from odoo import http, _
from odoo.exceptions import AccessDenied, AccessError, UserError, ValidationError
from odoo.http import request

_logger = logging.getLogger(__name__)


class TranscashPwaMyAccount(http.Controller):

    def _render(self, error=None, success=None):
        user = request.env.user
        return request.render('transcash_guias_api.tc_portal_my_account', {
            'account_user': user,
            'must_change': bool(request.env['tc.portal.password.state'].sudo().search_count([('user_id', '=', user.id), ('pending', '=', True)])),
            'message_error': error,
            'message_success': success,
            'csrf_token': request.csrf_token(),
        })

    @http.route('/transcash/mi-cuenta', type='http', auth='user', website=True,
                methods=['GET'], sitemap=False)
    def my_account(self, **kw):
        return self._render()

    @http.route('/transcash/mi-cuenta/contrasena', type='http', auth='user', website=True,
                methods=['POST'], csrf=True, sitemap=False)
    def change_password(self, **post):
        old = post.get('password_actual') or ''
        new = post.get('password_nueva') or ''
        confirm = post.get('password_confirmacion') or ''
        login = request.env.user.login or ''
        if not old:
            return self._render(error=_('Ingresa tu contraseña actual.'))
        login_key = re.sub(r'[^A-Z0-9]', '', login.upper())
        password_key = re.sub(r'[^A-Z0-9]', '', new.upper())
        if len(new) < 12 or password_key == login_key or new == old:
            return self._render(error=_('Utiliza una contraseña nueva de al menos 12 caracteres, distinta del usuario y de la actual.'))
        if new != confirm:
            return self._render(error=_('Las contraseñas nuevas no coinciden.'))
        try:
            # Método estándar: verifica la clave anterior. NO escribir password sudo.
            request.env['res.users'].change_password(old, new)
        except (AccessDenied, AccessError):
            return self._render(error=_('Contraseña actual incorrecta.'))
        except (UserError, ValidationError) as exc:
            return self._render(error=str(exc))
        pending = request.env['tc.portal.password.state'].sudo().search([
            ('user_id', '=', request.env.uid), ('pending', '=', True)])
        if pending:
            pending.write({'pending': False})
        _logger.info('Contraseña Transcash actualizada por usuario %s', request.env.uid)
        return self._render(success=_('Contraseña cambiada. Si tu sesión finaliza, vuelve a ingresar con la nueva clave.'))
