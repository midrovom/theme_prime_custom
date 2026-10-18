"""Página de inicio de la WebApp basada en los grupos efectivos del usuario."""
from odoo import http
from odoo.http import request

class TranscashLanding(http.Controller):
    @http.route(['/transcash', '/transcash/'], type='http', auth='user', website=True, methods=['GET'])
    def landing(self, **kw):
        user = request.env.user
        def group(short):
            return user.has_group('logistica_transcash.' + short)
        if not user.share:
            if group('group_logistica_manager') or group('group_transcash_operador_rutas'):
                target = '/transcash/operacion'
            elif group('group_transcash_consulta') or group('group_logistica_bodega') or group('group_transcash_contabilidad'):
                target = '/transcash/guias'
            elif group('group_transcash_dashboard'):
                return request.redirect('/web')
            else:
                return request.not_found()
        elif group('group_transcash_chofer'):
            target = '/transcash/embarques'
        elif group('group_transcash_transportista'):
            target = '/transcash/proveedor'
        elif group('group_transcash_cliente'):
            target = '/transcash/guias'
        else:
            return request.not_found()
        return request.redirect(target)
