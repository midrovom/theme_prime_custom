"""V5.24: Finanzas PWA para personal interno y visor de archivos protegidos.

No concede ninguna capacidad al chofer, al destinatario ni al Portal proveedor.
Los POST invocan la lógica de modelos, conservando sus locks y validaciones.
"""
import base64
import re
from html import unescape
from urllib.parse import quote

from odoo import http
from odoo.http import request
from odoo.exceptions import AccessError, UserError, ValidationError
from werkzeug.utils import secure_filename
from .evidence_hub import gallery_for_trip


class TranscashFinanzas(http.Controller):
    ERRORS = (UserError, AccessError, ValidationError, ValueError, TypeError)

    def _manager(self):
        user = request.env.user
        return not user.share and user.has_group('logistica_transcash.group_logistica_manager')

    def _accountant(self):
        user = request.env.user
        return not user.share and user.has_group('logistica_transcash.group_transcash_contabilidad')

    def _allowed(self):
        return self._manager() or self._accountant()

    def _trip(self, trip_id):
        if not self._allowed():
            return False
        trip = request.env['transcash.embarque'].sudo().browse(trip_id).exists()
        return trip if trip and trip.company_id in request.env.user.company_ids else False

    def _document(self, doc_id):
        if not self._allowed():
            return False
        doc = request.env['transcash.pago.liquidacion'].sudo().browse(doc_id).exists()
        return doc if doc and doc.company_id in request.env.user.company_ids else False

    @staticmethod
    def _history(record, limit=15):
        """Sólo para personal financiero autenticado, texto seguro sin HTML."""
        result = []
        for msg in record.message_ids.sorted('id', reverse=True)[:60]:
            clean = unescape(re.sub(r'<[^>]*>', ' ', str(msg.body or '')))
            clean = ' '.join(clean.split())
            if clean:
                result.append({'text': clean[:900], 'author': msg.author_id.name or 'Usuario',
                               'date': str(msg.date or '')})
            if len(result) == limit:
                break
        return result

    def _page(self, **kwargs):
        values = {'csrf_token': request.csrf_token(), 'can_manage': self._manager(),
                  'can_account': self._accountant(), 'error': None, 'ok': None}
        values.update(kwargs)
        response = request.render('logistica_transcash.portal_finanzas_transcash', values)
        response.headers['Cache-Control'] = 'private, no-store'
        return response

    def _return_error(self, url, exc):
        return request.redirect(url + ('&' if '?' in url else '?') + 'error=' + quote(str(exc)[:250]))

    @http.route('/transcash/finanzas', type='http', auth='user', website=True, methods=['GET'])
    def home(self, **kw):
        if not self._allowed():
            return request.not_found()
        comp = request.env.user.company_ids.ids
        trip_model = request.env['transcash.embarque'].sudo()
        docs_model = request.env['transcash.pago.liquidacion'].sudo()
        # Ambas bandejas son compañías autorizadas; la segunda solo incluye
        # facturas realmente presentadas (la liquidación en borrador va aparte).
        pending = trip_model.search([
            ('company_id', 'in', comp), ('estado_aprobacion', '=', 'aprobado'),
            ('liquidacion_linea_id', '=', False), ('legado_liquidacion_bloqueada', '=', False)
        ], order='id desc', limit=250)
        to_approve = trip_model.search([
            ('company_id', 'in', comp), ('state', '=', 'entregado'),
            ('estado_aprobacion', '=', 'pendiente')
        ], order='id desc', limit=250) if self._manager() else trip_model.browse()
        docs = docs_model.search([('company_id', 'in', comp)], order='id desc', limit=250)
        return self._page(section='inicio', pending=pending, to_approve=to_approve,
                          documents=docs, error=kw.get('error'), ok=kw.get('ok'))

    @http.route('/transcash/finanzas/embarques/<int:trip_id>', type='http', auth='user', website=True, methods=['GET'])
    def trip_detail(self, trip_id, **kw):
        trip = self._trip(trip_id)
        if not trip:
            return request.not_found()
        return self._page(section='trip', trip=trip, error=kw.get('error'),
                          ok=kw.get('ok'), history=self._history(trip), **gallery_for_trip(trip))

    @http.route('/transcash/finanzas/embarques/<int:trip_id>/negociar',
                type='http', auth='user', website=True, methods=['POST'], csrf=True)
    def negotiate(self, trip_id, **post):
        if not self._manager():
            return request.not_found()
        trip = self._trip(trip_id)
        if not trip:
            return request.not_found()
        base = '/transcash/finanzas/embarques/%d' % trip.id
        try:
            amount = float(post.get('precio') or 0)
            from math import isfinite
            if not isfinite(amount) or amount <= 0:
                raise UserError('Introduce un valor positivo válido.')
            if len((post.get('motivo') or '').strip()) < 5:
                raise UserError('Escribe el motivo de negociación (mínimo 5 caracteres).')
            wizard = request.env['transcash.tarifa.embarque.wizard'].create({
                'embarque_id': trip.id, 'valor_acordado': amount,
                'motivo': (post.get('motivo') or '').strip()[:1000]})
            wizard.action_confirm()
            return request.redirect(base + '?ok=negociado')
        except self.ERRORS as exc:
            return self._return_error(base, exc)

    @http.route('/transcash/finanzas/embarques/<int:trip_id>/aprobar',
                type='http', auth='user', website=True, methods=['POST'], csrf=True)
    def approve_trip(self, trip_id, **post):
        if not self._manager():
            return request.not_found()
        trip = self._trip(trip_id)
        if not trip:
            return request.not_found()
        base = '/transcash/finanzas/embarques/%d' % trip.id
        try:
            trip.action_approve_transport()
            return request.redirect(base + '?ok=aprobado')
        except self.ERRORS as exc:
            return self._return_error(base, exc)

    @http.route('/transcash/finanzas/liquidaciones/<int:doc_id>', type='http',
                auth='user', website=True, methods=['GET'])
    def document_detail(self, doc_id, **kw):
        doc = self._document(doc_id)
        if not doc:
            return request.not_found()
        return self._page(section='doc', doc=doc, error=kw.get('error'), ok=kw.get('ok'),
                          history=self._history(doc))

    @http.route('/transcash/finanzas/liquidaciones/<int:doc_id>/aprobar', type='http',
                auth='user', website=True, methods=['POST'], csrf=True)
    def approve_invoice(self, doc_id, **post):
        if not self._accountant():
            return request.not_found()
        doc = self._document(doc_id)
        if not doc:
            return request.not_found()
        base = '/transcash/finanzas/liquidaciones/%d' % doc.id
        try:
            # Model validates invoice == approved freight and exact state.
            doc.with_user(request.env.user).action_accounting_approve()
            return request.redirect(base + '?ok=aprobada')
        except self.ERRORS as exc:
            return self._return_error(base, exc)

    @http.route('/transcash/finanzas/liquidaciones/<int:doc_id>/observar', type='http',
                auth='user', website=True, methods=['POST'], csrf=True)
    def observe_invoice(self, doc_id, **post):
        if not self._accountant():
            return request.not_found()
        doc = self._document(doc_id)
        if not doc:
            return request.not_found()
        base = '/transcash/finanzas/liquidaciones/%d' % doc.id
        try:
            doc.with_user(request.env.user).action_accounting_observe(post.get('motivo') or '')
            return request.redirect(base + '?ok=observada')
        except self.ERRORS as exc:
            return self._return_error(base, exc)

    @http.route('/transcash/finanzas/liquidaciones/<int:doc_id>/pagar', type='http',
                auth='user', website=True, methods=['POST'], csrf=True)
    def register_payment(self, doc_id, **post):
        if not self._accountant():
            return request.not_found()
        doc = self._document(doc_id)
        if not doc:
            return request.not_found()
        base = '/transcash/finanzas/liquidaciones/%d' % doc.id
        try:
            upload = request.httprequest.files.get('comprobante')
            if not upload or not upload.filename:
                raise UserError('Adjunta el comprobante bancario de la transferencia.')
            data = upload.read(15 * 1024 * 1024 + 1)
            doc.with_user(request.env.user).action_register_payment(
                post.get('monto'), post.get('fecha_pago'), post.get('referencia'),
                post.get('medio'), base64.b64encode(data).decode('ascii'),
                secure_filename(upload.filename)[:180] or 'comprobante')
            return request.redirect(base + '?ok=pagada')
        except self.ERRORS as exc:
            return self._return_error(base, exc)

    def _inline(self, content, filename):
        blob = base64.b64decode(content)
        mime = ('application/pdf' if blob.startswith(b'%PDF-') else
                'image/png' if blob.startswith(b'\x89PNG\r\n\x1a\n') else 'image/jpeg')
        return request.make_response(blob, headers=[
            ('Content-Type', mime),
            ('Content-Disposition', 'inline; filename="%s"' % (secure_filename(filename or 'archivo') or 'archivo')),
            ('Cache-Control', 'private, no-store'),
            ('X-Content-Type-Options', 'nosniff'),
            ('X-Frame-Options', 'SAMEORIGIN')])

    @http.route('/transcash/finanzas/liquidaciones/<int:doc_id>/factura',
                type='http', auth='user', website=True, methods=['GET'])
    def invoice_preview(self, doc_id, **kw):
        doc = self._document(doc_id)
        if not doc or not doc.factura_archivo:
            return request.not_found()
        return self._inline(doc.factura_archivo, doc.factura_nombre)

    @http.route('/transcash/finanzas/pagos/<int:pago_id>/comprobante',
                type='http', auth='user', website=True, methods=['GET'])
    def receipt_preview(self, pago_id, **kw):
        if not self._allowed():
            return request.not_found()
        pago = request.env['transcash.pago.registro'].sudo().browse(pago_id).exists()
        if not pago or pago.company_id not in request.env.user.company_ids or not pago.comprobante:
            return request.not_found()
        return self._inline(pago.comprobante, pago.comprobante_nombre)
