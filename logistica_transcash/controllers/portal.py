"""Portal responsive para choferes y destinatarios autenticados.
No concede permisos generales sobre los modelos al grupo portal.
"""
import base64
from werkzeug.utils import secure_filename

from odoo import http, _
from odoo.exceptions import UserError, ValidationError
from odoo.http import request

MAX_FILE_SIZE = 10 * 1024 * 1024


class TranscashPortal(http.Controller):

    def _visible_domain(self):
        user = request.env.user
        partner = user.partner_id.commercial_partner_id
        return ['|', ('chofer_usuario_id', '=', user.id),
                ('destinatario_id', 'child_of', partner.id if partner else 0)]

    def _guide(self, guide_id):
        guia = request.env['transcash.guia'].sudo().browse(guide_id).exists()
        if not guia:
            return False
        user = request.env.user
        if guia.chofer_usuario_id.id != user.id and not guia._is_recipient(user):
            return False
        return guia

    def _render_guide(self, guia, error=None):
        return request.render('logistica_transcash.portal_guia_detalle', {
            'guia': guia,
            'es_chofer': guia.chofer_usuario_id.id == request.env.user.id,
            'es_receptor': guia._is_recipient(request.env.user),
            'evidencias': guia.evidencia_ids.sorted('create_date'),
            'error': error,
            'csrf_token': request.csrf_token(),
        })

    @http.route('/transcash/guias', type='http', auth='user', website=True, methods=['GET'])
    def guides(self, **kwargs):
        guides = request.env['transcash.guia'].sudo().search(self._visible_domain(),
                                                                order='create_date desc', limit=150)
        return request.render('logistica_transcash.portal_guias', {'guias': guides})

    @http.route('/transcash/guias/<int:guide_id>', type='http', auth='user', website=True, methods=['GET'])
    def guide_detail(self, guide_id, **kwargs):
        guia = self._guide(guide_id)
        if not guia:
            return request.not_found()
        return self._render_guide(guia)

    def _uploaded_file(self):
        file = request.httprequest.files.get('archivo')
        if not file or not file.filename:
            return False, False, False
        filename = secure_filename(file.filename)[:160]
        content = file.read(MAX_FILE_SIZE + 1)
        if len(content) > MAX_FILE_SIZE:
            raise UserError(_('El archivo excede el máximo de 10 MB.'))
        mime = False
        if content.startswith(b'\xff\xd8\xff'):
            mime = 'image/jpeg'
        elif content.startswith(b'\x89PNG\r\n\x1a\n'):
            mime = 'image/png'
        elif content.startswith(b'RIFF') and content[8:12] == b'WEBP':
            mime = 'image/webp'
        elif content.startswith(b'%PDF-'):
            mime = 'application/pdf'
        if not mime:
            raise UserError(_('Solo se admiten imágenes JPEG, PNG, WEBP o documentos PDF.'))
        return base64.b64encode(content).decode('ascii'), filename, mime

    @http.route('/transcash/guias/<int:guide_id>/evidencia', type='http', auth='user',
                website=True, methods=['POST'], csrf=True)
    def add_evidence(self, guide_id, **post):
        guia = self._guide(guide_id)
        if not guia:
            return request.not_found()
        try:
            b64, name, mime = self._uploaded_file()
            request.env['transcash.evidencia'].register_evidence(
                guia, (post.get('tipo') or '').strip(), post.get('observacion') or '',
                b64, name, mime, post.get('tipo_novedad') or 'ninguna')
        except (UserError, ValidationError, ValueError) as err:
            return self._render_guide(guia, str(err))
        return request.redirect('/transcash/guias/%s?ok=1' % guide_id)

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

    @http.route('/transcash/evidencia/<int:evidence_id>/revision/<string:decision>',
                type='http', auth='user', website=True, methods=['POST'], csrf=True)
    def review_evidence(self, evidence_id, decision, **post):
        ev = request.env['transcash.evidencia'].sudo().browse(evidence_id).exists()
        guia = self._guide(ev.guia_id.id) if ev else False
        if not guia:
            return request.not_found()
        if ev.tipo != 'llegada' or not guia._is_recipient(request.env.user):
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

    @http.route('/transcash/evidencia/<int:evidence_id>/respuesta',
                type='http', auth='user', website=True, methods=['POST'], csrf=True)
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
            guia.action_confirm_delivery(post.get('recibido_por'), post.get('observacion_recepcion'))
        except UserError as err:
            return self._render_guide(guia, str(err))
        return request.redirect('/transcash/guias/%s?ok=1' % guide_id)

    @http.route('/transcash/evidencia/<int:evidence_id>/archivo',
                type='http', auth='user', website=True, methods=['GET'])
    def file(self, evidence_id, **kwargs):
        ev = request.env['transcash.evidencia'].sudo().browse(evidence_id).exists()
        if not ev or not self._guide(ev.guia_id.id) or not ev.archivo:
            return request.not_found()
        mime = ev.archivo_mime or ''
        if mime not in ('image/jpeg', 'image/png', 'image/webp', 'application/pdf'):
            return request.not_found()
        filename = secure_filename(ev.archivo_nombre or 'evidencia')
        return request.make_response(base64.b64decode(ev.archivo), headers=[
            ('Content-Type', mime),
            ('X-Content-Type-Options', 'nosniff'),
            ('Cache-Control', 'private, no-store'),
            ('Content-Disposition', 'inline; filename="%s"' % filename),
        ])
