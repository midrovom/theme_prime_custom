"""Portal Mobile First: endpoints autenticados, CSRF, ACL específicos y media privada."""
import base64
import re
from werkzeug.utils import secure_filename
from odoo import http, _
from odoo.exceptions import UserError, ValidationError
from odoo.http import request
from .evidence_hub import gallery_for_guide

MB = 1024 * 1024
MAX_IMAGE = 12 * MB
MAX_VIDEO = 75 * MB
MAX_TOTAL = 110 * MB
MAX_FILES = 6
VIDEO_MIMES = ('video/mp4','video/quicktime','video/webm','video/3gpp')
IMAGE_MIMES = ('image/jpeg','image/png','image/webp','image/heic','image/heif')


def sniff_mime(content):
    if content.startswith(b'\xff\xd8\xff'):
        return 'image/jpeg'
    if content.startswith(b'\x89PNG\r\n\x1a\n'):
        return 'image/png'
    if content.startswith(b'RIFF') and content[8:12] == b'WEBP':
        return 'image/webp'
    if len(content) >= 12 and content[4:8] == b'ftyp':
        brand = content[8:12]
        if brand in (b'heic',b'heix',b'hevc',b'hevx'):
            return 'image/heic'
        if brand in (b'mif1', b'msf1'):
            return 'image/heif'
        if brand == b'qt  ':
            return 'video/quicktime'
        if brand.startswith(b'3g'):
            return 'video/3gpp'
        if brand in (b'isom',b'iso2',b'iso4',b'iso5',b'iso6',b'mp41',b'mp42',
                     b'avc1',b'M4V ',b'M4A ',b'dash'):
            return 'video/mp4'
    if content.startswith(b'\x1a\x45\xdf\xa3') and b'webm' in content[:128].lower():
        return 'video/webm'
    return False


class TranscashPortal(http.Controller):
    def _visible_domain(self):
        user = request.env.user
        partner = user.partner_id.commercial_partner_id
        if not user.share and (user.has_group('logistica_transcash.group_transcash_consulta') or
                               user.has_group('logistica_transcash.group_logistica_bodega') or
                               user.has_group('logistica_transcash.group_transcash_operador_rutas') or
                               user.has_group('logistica_transcash.group_logistica_manager')):
            return [('company_id','in', user.company_ids.ids)]
        recipient = ('destinatario_id', 'child_of', partner.id if partner else 0)
        # Portal cliente tiene prioridad incluso si hay grupos superpuestos:
        # nunca incluir guías ajenas a su destinatario.
        if user.has_group('logistica_transcash.group_transcash_cliente'):
            return [recipient]
        if user.has_group('logistica_transcash.group_transcash_chofer'):
            return ['|', ('chofer_usuario_id', '=', user.id), recipient]
        if user.has_group('logistica_transcash.group_transcash_transportista'):
            return [('proveedor_id.commercial_partner_id','=',partner.id if partner else 0)]
        return [recipient]

    def _guide(self, guide_id):
        guia = request.env['transcash.guia'].sudo().browse(guide_id).exists()
        if not guia:
            return False
        user = request.env.user
        if user.share and not any(user.has_group('logistica_transcash.%s' % role)
                for role in ('group_transcash_chofer','group_transcash_cliente','group_transcash_transportista')):
            return False
        if not user.share and not any(user.has_group('logistica_transcash.%s' % role)
                for role in ('group_transcash_operador_rutas', 'group_logistica_manager',
                             'group_logistica_bodega', 'group_transcash_consulta')):
            return False
        # Un Portal jamás adquiere lectura interna por tener accidentalmente grupos adicionales.
        if user.share:
            if user.has_group('logistica_transcash.group_transcash_cliente'):
                return guia if guia._is_recipient(user) else False
            if user.has_group('logistica_transcash.group_transcash_chofer'):
                return guia if guia.chofer_usuario_id.id == user.id else False
            if user.has_group('logistica_transcash.group_transcash_transportista'):
                return guia if guia.proveedor_id.commercial_partner_id == user.partner_id.commercial_partner_id else False
            return False
        if not (guia.chofer_usuario_id.id == user.id and user.has_group('logistica_transcash.group_transcash_chofer')) and not guia._is_recipient(user) and not (
                user.has_group('logistica_transcash.group_transcash_consulta') or
                user.has_group('logistica_transcash.group_logistica_bodega') or
                (not user.share and user.has_group('logistica_transcash.group_transcash_operador_rutas')) or
                (user.has_group('logistica_transcash.group_transcash_transportista') and
                 not user.has_group('logistica_transcash.group_transcash_chofer') and
                 not user.has_group('logistica_transcash.group_transcash_cliente') and
                 guia.proveedor_id.commercial_partner_id == user.partner_id.commercial_partner_id)):
            return False
        if guia.company_id not in user.company_ids and not user.share:
            return False
        return guia

    def _render_guide(self, guia, error=None):
        interno = not request.env.user.share and (
            request.env.user.has_group('logistica_transcash.group_transcash_consulta') or
            request.env.user.has_group('logistica_transcash.group_logistica_bodega') or
            request.env.user.has_group('logistica_transcash.group_transcash_operador_rutas'))
        historial = guia.evento_ids if interno else guia.evento_ids.filtered('publico_cliente')
        # No divulgar eventos operativos internos de versiones anteriores que
        # quedaron marcados por error como públicos antes de V5.19.
        if request.env.user.share and request.env.user.has_group('logistica_transcash.group_transcash_cliente'):
            private_starts = ('Asignada a hoja de ruta', 'Carga evidenciada por Logística',
                              'Chofer aceptó carga de hoja de ruta', 'Flete autorizado',
                              'Reasignación autorizada al confirmar hoja de ruta',
                              'Inicio de carga de la guía', 'Observación final de carga')
            historial = historial.filtered(lambda event: not any(
                (event.accion or '').startswith(prefix) for prefix in private_starts))
        return request.render('logistica_transcash.portal_guia_detalle', {
            'guia': guia,
            'es_chofer': bool(guia.chofer_usuario_id.id == request.env.user.id and
                              request.env.user.has_group('logistica_transcash.group_transcash_chofer') and
                              not (request.env.user.share and request.env.user.has_group('logistica_transcash.group_transcash_cliente'))),
            'carga_autonoma_habilitada': bool(request.env['transcash.chofer'].sudo().search([
                ('usuario_id','=',request.env.user.id), ('activo','=',True), ('carga_autonoma','=',True)],
                limit=1)) and request.env.user.has_group('logistica_transcash.group_transcash_chofer') and
                not (request.env.user.share and request.env.user.has_group('logistica_transcash.group_transcash_cliente')),
            'es_receptor': guia._is_recipient(request.env.user),
            'es_vendedor': guia._is_seller(request.env.user),
            'evidencias': guia.evidencia_ids.sorted('create_date', reverse=True),
            'roturas': guia.rotura_ids.sorted('create_date', reverse=True),
            'historial': historial.sorted('create_date', reverse=True)[:300],
            'csrf_token': request.csrf_token(), 'error': error,
            **gallery_for_guide(guia, is_recipient_only=bool(
                request.env.user.share and guia._is_recipient(request.env.user))),
        })

    @http.route('/transcash/guias', type='http', auth='user', website=True, methods=['GET'])
    def guides(self, **kwargs):
        user = request.env.user
        if user.share and not any(user.has_group('logistica_transcash.%s' % role)
                for role in ('group_transcash_chofer','group_transcash_cliente','group_transcash_transportista')):
            return request.render('logistica_transcash.portal_falta_perfil', {})
        if not user.share and not any(user.has_group('logistica_transcash.%s' % role)
                for role in ('group_transcash_operador_rutas', 'group_logistica_manager',
                             'group_logistica_bodega', 'group_transcash_consulta')):
            return request.render('logistica_transcash.portal_falta_perfil', {})
        # Cliente ve únicamente sus guías; chofer navega Embarque -> Ruta -> Guía.
        # Las URLs individuales de guía permanecen vigentes para entregas y sincronización offline.
        if user.share and user.has_group('logistica_transcash.group_transcash_chofer') and not user.has_group('logistica_transcash.group_transcash_cliente'):
            return request.redirect('/transcash/embarques')
        # Instalaciones PWA anteriores abrían /transcash/guias directamente.
        # Redirigir el inicio antiguo del operador a su centro funcional,
        # conservando el enlace explícito ?vista=consulta para consultar guías.
        if not user.share and (user.has_group('logistica_transcash.group_transcash_operador_rutas') or
                               user.has_group('logistica_transcash.group_logistica_manager')) and not (
                                   kwargs.get('estado') or kwargs.get('vista')):
            return request.redirect('/transcash/operacion')
        guides = request.env['transcash.guia'].sudo().search(
            self._visible_domain(), order='create_date desc', limit=150)
        selected = kwargs.get('estado') or 'todas'
        choices = ('todas','embarque','embarcada','ruta','destino','revision','entregada')
        if selected not in choices:
            selected = 'todas'
        if selected != 'todas':
            guides = guides.filtered(lambda g: g.state == selected)
        return request.render('logistica_transcash.portal_guias', {
            'guias': guides, 'estado_filtro': selected,
        })

    @http.route('/transcash/guias/<int:guide_id>', type='http', auth='user', website=True, methods=['GET'])
    def guide_detail(self, guide_id, **kwargs):
        guia = self._guide(guide_id)
        return self._render_guide(guia) if guia else request.not_found()

    @http.route('/transcash/guias/<int:guide_id>/galeria-viaje', type='http',
                auth='user', website=True, methods=['GET'])
    def guide_evidence_hub(self, guide_id, **kw):
        guide = self._guide(guide_id)
        if not guide:
            return request.not_found()
        only_own = bool(request.env.user.share and guide._is_recipient(request.env.user))
        response = request.render('logistica_transcash.transcash_evidence_hub_page', {
            'gallery_page_title':guide.name,
            'gallery_back_url':'/transcash/guias/%d' % guide.id,
            'embedded':kw.get('embedded') == '1',
            **gallery_for_guide(guide, is_recipient_only=only_own),
        })
        response.headers['Cache-Control'] = 'private, no-store'
        return response

    def _uploaded_files(self):
        uploads = request.httprequest.files.getlist('archivos')
        uploads += request.httprequest.files.getlist('archivo')  # Formularios de versión anterior
        uploads = [u for u in uploads if u and u.filename]
        if len(uploads) > MAX_FILES:
            raise UserError(_('Máximo seis fotos o videos por registro.'))
        files = []
        total = 0
        for upload in uploads:
            content = upload.read(MAX_VIDEO + 1)
            if len(content) > MAX_VIDEO:
                raise UserError(_('Video demasiado grande: máximo 75 MB.'))
            mime = sniff_mime(content)
            if mime not in IMAGE_MIMES + VIDEO_MIMES:
                raise UserError(_('Formato no válido. Use JPG, PNG, WEBP, HEIC, MP4, MOV o WEBM.'))
            if mime in IMAGE_MIMES and len(content) > MAX_IMAGE:
                raise UserError(_('Fotografía demasiado grande: máximo 12 MB.'))
            total += len(content)
            if total > MAX_TOTAL:
                raise UserError(_('El total de la carga supera 110 MB.'))
            files.append((base64.b64encode(content).decode('ascii'),
                          secure_filename(upload.filename)[:160] or 'media', mime))
        return files

    @http.route('/transcash/guias/<int:guide_id>/evidencia', type='http', auth='user',
                website=True, methods=['POST'], csrf=True)
    def add_evidence(self, guide_id, **post):
        guia = self._guide(guide_id)
        if not guia:
            return request.not_found()
        try:
            tipo = (post.get('tipo') or '').strip()
            if post.get('tipo_novedad') == 'rotura':
                raise UserError(_('Para reportar roturas utilice el formulario por producto.'))
            files = self._uploaded_files()
            if tipo in ('carga','llegada') and not files:
                raise UserError(_('Adjunte al menos una foto o video.'))
            note = (post.get('observacion') or '').strip()
            if tipo == 'llegada' and not note:
                note = 'Evidencia de descarga sin novedades declaradas por el chofer'
            if tipo == 'cliente' and not note and files and post.get('tipo_novedad', 'ninguna') == 'ninguna':
                note = 'Fotografía o video de recepción aportado por el destinatario'
            for file in (files or [(False,False,False)]):
                request.env['transcash.evidencia'].register_evidence(
                    guia, tipo, note, *file,
                    post.get('tipo_novedad') or 'ninguna')
        except (UserError, ValidationError, ValueError) as err:
            return self._render_guide(guia, str(err))
        return request.redirect('/transcash/guias/%s?ok=1' % guide_id)

    @http.route('/transcash/guias/<int:guide_id>/rotura', type='http', auth='user',
                website=True, methods=['POST'], csrf=True)
    def add_damage(self, guide_id, **post):
        guia = self._guide(guide_id)
        if not guia:
            return request.not_found()
        try:
            line_id = int(post.get('linea_id') or '0')
            line = guia.linea_ids.filtered(lambda l: l.id == line_id and l.vigente_erp)[:1]
            request.env['transcash.rotura'].register_damage(
                guia, line, post.get('cantidad_rota'), post.get('observacion') or '',
                self._uploaded_files())
        except (UserError, ValidationError, ValueError, TypeError) as err:
            return self._render_guide(guia, str(err))
        return request.redirect('/transcash/guias/%s?ok=1#roturas' % guide_id)

    @http.route('/transcash/guias/<int:guide_id>/llegada', type='http', auth='user',
                website=True, methods=['POST'], csrf=True)
    def arrive(self, guide_id, **post):
        guia = self._guide(guide_id)
        if not guia:
            return request.not_found()
        try:
            guia.action_arrive()
        except UserError as err:
            return self._render_guide(guia, str(err))
        return request.redirect('/transcash/guias/%s?ok=1' % guide_id)

    @http.route('/transcash/guias/<int:guide_id>/finalizar-entrega', type='http', auth='user',
                website=True, methods=['POST'], csrf=True)
    def close_driver_delivery(self, guide_id, **post):
        guia = self._guide(guide_id)
        if not guia:
            return request.not_found()
        try:
            guia.action_close_driver_delivery(post.get('observacion') or '', post.get('persona_presente') or '', post.get('firma_png') or '')
        except (UserError, ValidationError) as err:
            return self._render_guide(guia, str(err))
        # Llevar al conductor a la siguiente entrega pendiente, sin pasos extra.
        trip = guia.embarque_id
        if trip:
            following = trip.guia_ids.filtered(lambda g: g.id != guia.id and
                g.state in ('ruta','destino') and not g.fecha_cierre_chofer)
            if following:
                return request.redirect('/transcash/guias/%d?ok=1' % following[0].id)
            return request.redirect('/transcash/embarques/%d?ok=1' % trip.id)
        return request.redirect('/transcash/guias/%d?ok=1' % guide_id)

    @http.route('/transcash/evidencia/<int:evidence_id>/revision/<string:decision>',
                type='http', auth='user', website=True, methods=['POST'], csrf=True)
    def review_evidence(self, evidence_id, decision, **post):
        ev = request.env['transcash.evidencia'].sudo().browse(evidence_id).exists()
        guia = self._guide(ev.guia_id.id) if ev else False
        if not guia or ev.tipo != 'llegada' or not guia._is_recipient(request.env.user):
            return request.not_found()
        try:
            if decision == 'aprobar':
                ev.action_approve()
            elif decision == 'objetar':
                ev.object_evidence(post.get('motivo') or '')
            else:
                return request.not_found()
        except UserError as err:
            return self._render_guide(guia, str(err))
        return request.redirect('/transcash/guias/%s?ok=1' % guia.id)

    @http.route('/transcash/evidencia/<int:evidence_id>/respuesta', type='http',
                auth='user', website=True, methods=['POST'], csrf=True)
    def answer(self, evidence_id, **post):
        ev = request.env['transcash.evidencia'].sudo().browse(evidence_id).exists()
        guia = self._guide(ev.guia_id.id) if ev else False
        if not guia or guia.chofer_usuario_id.id != request.env.user.id:
            return request.not_found()
        try:
            ev.answer_objection(post.get('respuesta') or '')
        except UserError as err:
            return self._render_guide(guia, str(err))
        return request.redirect('/transcash/guias/%s?ok=1' % guia.id)

    @http.route('/transcash/guias/<int:guide_id>/confirmar', type='http', auth='user',
                website=True, methods=['POST'], csrf=True)
    def confirm(self, guide_id, **post):
        guia = self._guide(guide_id)
        if not guia or not guia._is_recipient(request.env.user):
            return request.not_found()
        try:
            guia.action_confirm_delivery(post.get('recibido_por'), post.get('observacion_recepcion'), post.get('resultado') or 'conforme')
        except UserError as err:
            return self._render_guide(guia, str(err))
        return request.redirect('/transcash/guias/%s?ok=1' % guide_id)

    @http.route('/transcash/evidencia/<int:evidence_id>/archivo', type='http', auth='user',
                website=True, methods=['GET'])
    def file(self, evidence_id, **kwargs):
        ev = request.env['transcash.evidencia'].sudo().browse(evidence_id).exists()
        if not ev or not self._guide(ev.guia_id.id) or not ev.archivo:
            return request.not_found()
        mime = ev.archivo_mime or ''
        if mime not in IMAGE_MIMES + VIDEO_MIMES:
            return request.not_found()
        data = base64.b64decode(ev.archivo)
        filename = secure_filename(ev.archivo_nombre or 'evidencia')
        headers = [('Content-Type', mime), ('X-Content-Type-Options','nosniff'),
                   ('Cache-Control','private, no-store'),('Accept-Ranges','bytes'),
                   ('Content-Disposition','inline; filename="%s"' % filename)]
        byte_range = request.httprequest.headers.get('Range', '')
        if byte_range:
            m = re.fullmatch(r'bytes=(\d*)-(\d*)', byte_range.strip())
            if not m or (not m.group(1) and not m.group(2)):
                return request.make_response(b'', headers=[('Content-Range','bytes */%d' % len(data))], status=416)
            start = int(m.group(1)) if m.group(1) else max(0, len(data) - int(m.group(2)))
            end = int(m.group(2)) if m.group(2) else len(data) - 1
            end = min(end, len(data)-1)
            if start > end or start >= len(data):
                return request.make_response(b'', headers=[('Content-Range','bytes */%d' % len(data))], status=416)
            headers.extend([('Content-Range','bytes %s-%s/%s' % (start,end,len(data))),
                            ('Content-Length',str(end-start+1))])
            return request.make_response(data[start:end+1], headers=headers, status=206)
        headers.append(('Content-Length',str(len(data))))
        return request.make_response(data, headers=headers)
