"""WebApp: vista de embarques exclusivamente para chofer y usuarios internos."""
from odoo import http, _
from urllib.parse import quote
from odoo.exceptions import UserError, AccessError, ValidationError
from odoo.http import request
from .portal import TranscashPortal


class EmbarquePortal(TranscashPortal):
    def _can_see_embark(self, rec):
        user = request.env.user
        if not rec:
            return False
        if user.has_group('logistica_transcash.group_transcash_chofer') and rec.chofer_usuario_id.id == user.id:
            return True
        if user.has_group('logistica_transcash.group_transcash_transportista') and rec.proveedor_id.commercial_partner_id == user.partner_id.commercial_partner_id:
            return True
        return bool(not user.share and rec.company_id in user.company_ids and (
            user.has_group('logistica_transcash.group_transcash_consulta') or
            user.has_group('logistica_transcash.group_logistica_bodega')))

    def _get(self, embark_id):
        rec = request.env['transcash.embarque'].sudo().browse(embark_id).exists()
        return rec if self._can_see_embark(rec) else False

    def _render(self, rec, error=None):
        driver = (request.env.user.has_group('logistica_transcash.group_transcash_chofer') and
                  rec.chofer_usuario_id.id == request.env.user.id)
        return request.render('logistica_transcash.portal_embarque_detalle', {
            'embarque':rec, 'es_chofer':driver, 'error':error,
            'csrf_token':request.csrf_token(),
        })

    @http.route('/transcash/embarques', type='http', auth='user', website=True, methods=['GET'])
    def list_embarks(self, **kw):
        user = request.env.user
        if user.has_group('logistica_transcash.group_transcash_chofer'):
            domain = [('chofer_usuario_id','=',user.id)]
        elif user.has_group('logistica_transcash.group_transcash_transportista'):
            domain = [('proveedor_id.commercial_partner_id','=',user.partner_id.commercial_partner_id.id)]
        elif not user.share and (user.has_group('logistica_transcash.group_transcash_consulta') or
                                  user.has_group('logistica_transcash.group_logistica_bodega')):
            domain = [('company_id','in',user.company_ids.ids)]
        else:
            return request.not_found()
        recs = request.env['transcash.embarque'].sudo().search(domain, order='create_date desc', limit=100)
        disponibles = request.env['transcash.guia'].sudo()
        if user.has_group('logistica_transcash.group_transcash_chofer'):
            disponibles = disponibles.search([
                ('chofer_usuario_id','=',user.id),('state','=','registrada'),
                ('embarque_id','=',False), ('proveedor_id','!=',False),
            ], order='create_date desc', limit=100)
        return request.render('logistica_transcash.portal_embarques', {
            'embarques':recs,'disponibles':disponibles,'csrf_token':request.csrf_token(),
            'es_chofer': user.has_group('logistica_transcash.group_transcash_chofer'),
            'error':kw.get('error'),
        })

    @http.route('/transcash/embarques/crear',type='http',auth='user',website=True,methods=['POST'],csrf=True)
    def create_embark(self, **post):
        try:
            ids = request.httprequest.form.getlist('guias')
            embarque = request.env['transcash.embarque'].create_from_guides(ids, post.get('observacion') or '')
        except (UserError, AccessError, ValidationError, ValueError) as err:
            # Show clean error without writing side effects to database.
            return request.redirect('/transcash/embarques?error=' + quote(str(err)[:250]))
        return request.redirect('/transcash/embarques/%s?ok=1' % embarque.id)

    @http.route('/transcash/embarques/<int:embark_id>',type='http',auth='user',website=True,methods=['GET'])
    def embark_detail(self, embark_id, **kw):
        embarque = self._get(embark_id)
        return self._render(embarque) if embarque else request.not_found()

    @http.route('/transcash/embarques/<int:embark_id>/guia/<int:guide_id>/<string:operation>',
                type='http',auth='user',website=True,methods=['POST'],csrf=True)
    def guide_operation(self, embark_id, guide_id, operation, **post):
        embarque = self._get(embark_id)
        if not embarque:
            return request.not_found()
        try:
            record = embarque
            if operation == 'iniciar':
                record.action_begin_guide(guide_id, post.get('observacion') or '')
            elif operation == 'finalizar':
                record.action_finish_guide(guide_id, post.get('observacion') or '')
            else:
                return request.not_found()
        except (UserError, AccessError, ValidationError) as err:
            return self._render(embarque, str(err))
        return request.redirect('/transcash/embarques/%s?ok=1' % embark_id)

    @http.route('/transcash/embarques/<int:embark_id>/embarcar',type='http',auth='user',website=True,methods=['POST'],csrf=True)
    def finish_embark(self, embark_id, **post):
        embarque = self._get(embark_id)
        if not embarque:
            return request.not_found()
        try:
            embarque.action_mark_embarked()
        except (UserError, AccessError, ValidationError) as err:
            return self._render(embarque, str(err))
        return request.redirect('/transcash/embarques/%s?ok=1' % embark_id)
