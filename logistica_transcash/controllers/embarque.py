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
            user.has_group('logistica_transcash.group_logistica_bodega') or
            user.has_group('logistica_transcash.group_transcash_operador_rutas')))

    def _get(self, embark_id):
        rec = request.env['transcash.embarque'].sudo().browse(embark_id).exists()
        return rec if self._can_see_embark(rec) else False

    def _late_guides(self, embark):
        """Guías recientes disponibles que comparten chofer, empresa y placa."""
        user = request.env.user
        if not (user.has_group('logistica_transcash.group_transcash_chofer') and
                embark.chofer_usuario_id == user and embark.state == 'preparacion'):
            return request.env['transcash.guia'].sudo().browse()
        items = request.env['transcash.guia'].sudo().search([
            ('chofer_usuario_id', '=', user.id),
            ('state', '=', 'registrada'), ('embarque_id', '=', False),
            ('company_id', '=', embark.company_id.id),
            ('proveedor_id', '=', embark.proveedor_id.id),
        ], order='create_date desc', limit=200)
        placa = (embark.placa or '').strip().upper()
        return items.filtered(lambda g: (g.placa or '').strip().upper() == placa)[:100]

    def _render(self, rec, error=None):
        driver = (request.env.user.share and request.env.user.has_group('logistica_transcash.group_transcash_chofer') and
                  rec.chofer_usuario_id.id == request.env.user.id)
        return request.render('logistica_transcash.portal_embarque_detalle', {
            'embarque':rec, 'es_chofer':driver, 'error':error,
            'guias_adicionales': self._late_guides(rec) if driver else request.env['transcash.guia'].sudo().browse(),
            'csrf_token':request.csrf_token(),
        })

    @http.route('/transcash/embarques', type='http', auth='user', website=True, methods=['GET'])
    def list_embarks(self, **kw):
        user = request.env.user
        if not user.share and (user.has_group('logistica_transcash.group_transcash_operador_rutas') or
                               user.has_group('logistica_transcash.group_logistica_manager')):
            domain = [('company_id','in',user.company_ids.ids)]
        elif user.has_group('logistica_transcash.group_transcash_chofer') and user.share:
            domain = [('chofer_usuario_id','=',user.id)]
        elif user.has_group('logistica_transcash.group_transcash_transportista') and user.share:
            domain = [('proveedor_id.commercial_partner_id','=',user.partner_id.commercial_partner_id.id)]
        elif not user.share and (user.has_group('logistica_transcash.group_transcash_consulta') or
                                  user.has_group('logistica_transcash.group_logistica_bodega')):
            domain = [('company_id','in',user.company_ids.ids)]
        else:
            return request.not_found()
        recs = request.env['transcash.embarque'].sudo().search(domain, order='create_date desc', limit=100)
        activo = request.env['transcash.embarque'].sudo().browse()
        if user.share and user.has_group('logistica_transcash.group_transcash_chofer'):
            activo = request.env['transcash.embarque'].sudo().search([
                ('chofer_usuario_id', '=', user.id),
                ('state', 'in', ['preparacion','embarcado','ruta']),
            ], order='create_date desc', limit=1)
        disponibles = request.env['transcash.guia'].sudo()
        if user.share and user.has_group('logistica_transcash.group_transcash_chofer'):
            disponibles = disponibles.search([
                ('chofer_usuario_id','=',user.id),('state','=','registrada'),
                ('embarque_id','=',False), ('proveedor_id','!=',False),
            ], order='create_date desc', limit=100)
        return request.render('logistica_transcash.portal_embarques', {
            'embarques':recs,'disponibles':disponibles,'embarque_activo':activo,
            'csrf_token':request.csrf_token(),
            'es_chofer': user.share and user.has_group('logistica_transcash.group_transcash_chofer'),
            'es_operador': not user.share and (user.has_group('logistica_transcash.group_transcash_operador_rutas') or user.has_group('logistica_transcash.group_logistica_manager')),
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

    @http.route('/transcash/embarques/<int:embark_id>/guias/agregar',
                type='http', auth='user', website=True, methods=['POST'], csrf=True)
    def add_guides(self, embark_id, **post):
        embarque = self._get(embark_id)
        if not embarque:
            return request.not_found()
        try:
            ids = request.httprequest.form.getlist('guias')
            embarque.action_add_guides(ids)
        except (UserError, AccessError, ValidationError, ValueError) as err:
            return self._render(embarque, str(err))
        return request.redirect('/transcash/embarques/%s?ok=1#tc-add-guides' % embark_id)

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
            if post.get('return_to') == 'guia':
                guia = self._guide(guide_id)
                if guia:
                    return self._render_guide(guia, str(err))
            return self._render(embarque, str(err))
        if post.get('return_to') == 'guia':
            return request.redirect('/transcash/guias/%s?ok=1' % guide_id)
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

class AceptacionCargaController(http.Controller):
    def _get(self, embark_id):
        return EmbarquePortal()._get(embark_id)

    def _render(self, embark, error=None):
        return EmbarquePortal()._render(embark, error)

    @http.route('/transcash/embarques/<int:embark_id>/aceptar-salir',
                type='http', auth='user', website=True, methods=['POST'], csrf=True)
    def accept_depart(self, embark_id, **post):
        emb = self._get(embark_id)
        if not emb:
            return request.not_found()
        try:
            emb.action_accept_and_depart()
        except (UserError, AccessError, ValidationError) as err:
            return self._render(emb, str(err))
        return request.redirect('/transcash/embarques/%d?ok=1' % emb.id)

    @http.route('/transcash/embarques/<int:embark_id>/observar',
                type='http', auth='user', website=True, methods=['POST'], csrf=True)
    def dispute_packing(self, embark_id, **post):
        emb = self._get(embark_id)
        if not emb:
            return request.not_found()
        try:
            emb.action_report_discrepancy(post.get('motivo') or '')
        except (UserError, AccessError, ValidationError) as err:
            return self._render(emb, str(err))
        return request.redirect('/transcash/embarques/%d?ok=1' % emb.id)

    @http.route('/transcash/rutas/evidencia/<int:evidencia_id>',
                type='http', auth='user', website=True, methods=['GET'])
    def ruta_evidencia(self, evidencia_id, **kw):
        import base64
        import re
        from werkzeug.utils import secure_filename
        evidence = request.env['transcash.carga.evidencia.ruta'].sudo().browse(evidencia_id).exists()
        if not evidence or not evidence.archivo:
            return request.not_found()
        route = evidence.ruta_id
        user = request.env.user
        allowed = ((user.has_group('logistica_transcash.group_transcash_chofer') and
                    route.chofer_usuario_id == user) or
                   (user.has_group('logistica_transcash.group_transcash_transportista') and
                    route.proveedor_id.commercial_partner_id == user.partner_id.commercial_partner_id) or
                   (not user.share and route.company_id in user.company_ids and
                    (user.has_group('logistica_transcash.group_transcash_consulta') or
                     user.has_group('logistica_transcash.group_logistica_bodega') or
                     user.has_group('logistica_transcash.group_transcash_operador_rutas') or
                     user.has_group('logistica_transcash.group_logistica_manager'))))
        if not allowed or evidence.mime not in ('image/jpeg','image/png','image/webp','image/heic','image/heif',
                                               'video/mp4','video/webm','video/quicktime'):
            return request.not_found()
        data = base64.b64decode(evidence.archivo)
        headers = [('Content-Type',evidence.mime),('X-Content-Type-Options','nosniff'),
                   ('Cache-Control','private, no-store'),
                   ('Content-Disposition','inline; filename="%s"' % secure_filename(evidence.nombre or 'evidencia')),
                   ('Accept-Ranges','bytes')]
        range_header = request.httprequest.headers.get('Range','')
        if range_header and evidence.tipo == 'video':
            match = re.fullmatch(r'bytes=(\d*)-(\d*)', range_header.strip())
            if not match or not any(match.groups()):
                return request.make_response(b'',headers=[('Content-Range','bytes */%d'%len(data))],status=416)
            start = int(match.group(1)) if match.group(1) else max(0,len(data)-int(match.group(2)))
            end = min(int(match.group(2)),len(data)-1) if match.group(2) else len(data)-1
            if start > end or start >= len(data):
                return request.make_response(b'',headers=[('Content-Range','bytes */%d'%len(data))],status=416)
            headers += [('Content-Range','bytes %d-%d/%d'%(start,end,len(data))),
                        ('Content-Length',str(end-start+1))]
            return request.make_response(data[start:end+1],headers=headers,status=206)
        headers.append(('Content-Length',str(len(data))))
        return request.make_response(data,headers=headers)

    @http.route('/transcash/rutas/<int:ruta_id>/video',
                type='http', auth='user', website=True, methods=['GET'])
    def video_route(self, ruta_id, **kw):
        import base64
        from werkzeug.utils import secure_filename
        ruta = request.env['transcash.hoja.ruta'].sudo().browse(ruta_id).exists()
        if not ruta or ruta.state not in ('cargada','aceptada') or not ruta.video_carga:
            return request.not_found()
        user = request.env.user
        authorized = ((user.has_group('logistica_transcash.group_transcash_chofer') and
                       ruta.chofer_usuario_id == user) or
                      (user.has_group('logistica_transcash.group_transcash_transportista') and
                       ruta.proveedor_id.commercial_partner_id == user.partner_id.commercial_partner_id) or
                      (not user.share and ruta.company_id in user.company_ids and
                       (user.has_group('logistica_transcash.group_transcash_consulta') or
                        user.has_group('logistica_transcash.group_transcash_operador_rutas'))))
        if not authorized:
            return request.not_found()
        data = base64.b64decode(ruta.video_carga)
        mime = ruta.video_mime
        if mime not in ('video/mp4', 'video/webm', 'video/quicktime'):
            return request.not_found()
        headers = [('Content-Type',mime),('X-Content-Type-Options','nosniff'),
                   ('Cache-Control','private, no-store'),
                   ('Content-Disposition','inline; filename="%s"' % secure_filename(ruta.video_nombre or 'carga.mp4')),
                   ('Accept-Ranges','bytes')]
        import re
        range_header = request.httprequest.headers.get('Range', '')
        if range_header:
            match = re.fullmatch(r'bytes=(\d*)-(\d*)', range_header.strip())
            if not match or (not match.group(1) and not match.group(2)):
                return request.make_response(b'', headers=[('Content-Range','bytes */%d' % len(data))], status=416)
            start = int(match.group(1)) if match.group(1) else max(0,len(data)-int(match.group(2)))
            end = min(int(match.group(2)),len(data)-1) if match.group(2) else len(data)-1
            if start < 0 or start > end or start >= len(data):
                return request.make_response(b'', headers=[('Content-Range','bytes */%d' % len(data))], status=416)
            headers += [('Content-Range','bytes %d-%d/%d'%(start,end,len(data))),
                        ('Content-Length',str(end-start+1))]
            return request.make_response(data[start:end+1],headers=headers,status=206)
        headers.append(('Content-Length',str(len(data))))
        return request.make_response(data,headers=headers)

class FirmaController(http.Controller):
    @http.route('/transcash/guias/<int:guide_id>/firma', type='http', auth='user', website=True, methods=['GET'])
    def guide_signature(self, guide_id, **kw):
        import base64
        guide = TranscashPortal()._guide(guide_id)
        if not guide or not guide.firma_receptor:
            return request.not_found()
        data = base64.b64decode(guide.firma_receptor)
        if not data.startswith(b'\x89PNG\r\n\x1a\n'):
            return request.not_found()
        return request.make_response(data, headers=[
            ('Content-Type','image/png'),('X-Content-Type-Options','nosniff'),
            ('Cache-Control','private, no-store'),('Content-Disposition','inline')])
