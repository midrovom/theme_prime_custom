"""Entrada Transcash por rol; un Portal sin grupo no queda con un 404 ambiguo."""
from odoo import http
from odoo.http import request


class TranscashLanding(http.Controller):
    @staticmethod
    def _home_for_user(user):
        def group(short):
            return user.has_group('logistica_transcash.' + short)
        if user.share:
            # Ante grupos Portal incompatibles, prima el menor privilegio: cliente.
            if group('group_transcash_cliente'):
                return '/transcash/guias'
            if group('group_transcash_chofer'):
                return '/transcash/embarques'
            if group('group_transcash_transportista'):
                return '/transcash/proveedor'
            return False
        if group('group_logistica_manager') or group('group_transcash_operador_rutas'):
            return '/transcash/operacion'
        if group('group_transcash_contabilidad'):
            return '/transcash/finanzas'
        if group('group_transcash_consulta') or group('group_logistica_bodega'):
            return '/transcash/guias'
        if group('group_transcash_dashboard'):
            return '/web'
        return False

    @staticmethod
    def _role_help():
        return request.render('logistica_transcash.portal_falta_perfil', {})

    @http.route(['/transcash', '/transcash/'], type='http', auth='user', website=True, methods=['GET'])
    def landing(self, **kw):
        target = self._home_for_user(request.env.user)
        if not target:
            return self._role_help()
        return request.redirect(target)

    # Alias de entrada para enlaces guardados en móviles y contactos de clientes.
    # No concede permisos: el acceso a las guías se valida nuevamente en /transcash/guias.
    @http.route(['/transcash/cliente', '/transcash/recepcion', '/transcash/recepciones'],
                type='http', auth='user', website=True, methods=['GET'])
    def client_entry(self, **kw):
        user = request.env.user
        if user.share and user.has_group('logistica_transcash.group_transcash_cliente'):
            return request.redirect('/transcash/guias')
        return request.redirect('/transcash')
