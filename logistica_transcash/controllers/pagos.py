"""Portal de solo lectura de embarques y autogestión DOCUMENTAL del proveedor.
Ninguna ruta concede ACL a portal ni publica archivos sin validar propiedad.
"""
import base64
from urllib.parse import quote
from werkzeug.utils import secure_filename
from odoo import http
from odoo.http import request
from odoo.exceptions import UserError, AccessError, ValidationError


class TranscashSupplier(http.Controller):
    def _supplier(self):
        u = request.env.user
        if (not u.share or not u.has_group('logistica_transcash.group_transcash_transportista') or
                u.has_group('logistica_transcash.group_transcash_chofer') or
                u.has_group('logistica_transcash.group_transcash_cliente') or
                not u.partner_id or not u.partner_id.commercial_partner_id):
            return False
        return u.partner_id.commercial_partner_id

    def _doc(self, doc_id):
        supplier = self._supplier()
        if not supplier:
            return False
        rec = request.env['transcash.pago.liquidacion'].sudo().browse(doc_id).exists()
        return rec if rec and rec.proveedor_id.commercial_partner_id == supplier else False

    def _page(self, template, **data):
        return request.render(template, dict(data, csrf_token=request.csrf_token()))

    @http.route('/transcash/proveedor', type='http', auth='user', website=True, methods=['GET'])
    def supplier_dashboard(self, **kw):
        supplier = self._supplier()
        if not supplier:
            return request.not_found()
        trips = request.env['transcash.embarque'].sudo().search([
            ('proveedor_id.commercial_partner_id', '=', supplier.id)], order='create_date desc', limit=250)
        documents = request.env['transcash.pago.liquidacion'].sudo().search([
            ('proveedor_id.commercial_partner_id', '=', supplier.id)], order='id desc', limit=100)
        available = trips.filtered(lambda t: t.estado_aprobacion == 'aprobado' and
                                   not t.liquidacion_linea_id and t.valor_acordado > 0)
        return self._page('logistica_transcash.portal_proveedor_inicio', trips=trips,
                          documents=documents, available=available,
                          error=kw.get('error'), ok=kw.get('ok'))

    @http.route('/transcash/proveedor/liquidaciones/crear', type='http', auth='user', website=True,
                methods=['POST'], csrf=True)
    def supplier_create(self, **post):
        if not self._supplier():
            return request.not_found()
        try:
            ids = request.httprequest.form.getlist('embarques')
            doc = request.env['transcash.pago.liquidacion'].create_supplier_liquidation(ids)
            return request.redirect('/transcash/proveedor/liquidaciones/%d' % doc.id)
        except (UserError, AccessError, ValidationError, ValueError) as exc:
            return request.redirect('/transcash/proveedor?error=' + quote(str(exc)[:220]))

    @http.route('/transcash/proveedor/liquidaciones/<int:doc_id>', type='http', auth='user',
                website=True, methods=['GET'])
    def supplier_detail(self, doc_id, **post):
        doc = self._doc(doc_id)
        return (self._page('logistica_transcash.portal_proveedor_liquidacion', doc=doc,
                           error=post.get('error'), ok=post.get('ok')) if doc else request.not_found())

    @http.route('/transcash/proveedor/liquidaciones/<int:doc_id>/factura', type='http',
                auth='user', website=True, methods=['POST'], csrf=True)
    def supplier_invoice(self, doc_id, **post):
        doc = self._doc(doc_id)
        if not doc:
            return request.not_found()
        try:
            upload = request.httprequest.files.get('factura')
            if not upload or not upload.filename:
                raise UserError('Adjunte la factura del proveedor.')
            blob = upload.read(15 * 1024 * 1024 + 1)
            doc.action_supplier_submit(post.get('numero'), post.get('fecha'),
                post.get('subtotal'), post.get('impuestos', '0'),
                base64.b64encode(blob).decode('ascii'),
                secure_filename(upload.filename)[:180] or 'factura',post.get('nota') or '')
            return request.redirect('/transcash/proveedor/liquidaciones/%d?ok=1' % doc.id)
        except (UserError, AccessError, ValidationError, ValueError) as exc:
            return request.redirect('/transcash/proveedor/liquidaciones/%d?error=%s' % (doc.id,quote(str(exc)[:220])))

    @http.route('/transcash/proveedor/liquidaciones/<int:doc_id>/factura/archivo',
                type='http', auth='user', website=True, methods=['GET'])
    def invoice_download(self, doc_id, **kw):
        doc = self._doc(doc_id)
        if not doc or not doc.factura_archivo:
            return request.not_found()
        blob = base64.b64decode(doc.factura_archivo)
        mime = ('application/pdf' if blob.startswith(b'%PDF-') else
                'image/png' if blob.startswith(b'\x89PNG') else 'image/jpeg')
        return request.make_response(blob, headers=[('Content-Type',mime),
            ('Content-Disposition','inline; filename="%s"' % (secure_filename(doc.factura_nombre or 'factura') or 'factura')),
            ('X-Content-Type-Options','nosniff'),('Cache-Control','private, no-store')])

    @http.route('/transcash/proveedor/liquidaciones/<int:doc_id>/imprimir',
                type='http', auth='user', website=True, methods=['GET'])
    def supplier_print(self, doc_id, **kw):
        doc = self._doc(doc_id)
        if not doc:
            return request.not_found()
        pdf, _ = request.env['ir.actions.report'].sudo()._render_qweb_pdf(
            'logistica_transcash.action_report_pago_liquidacion', [doc.id])
        return request.make_response(pdf, headers=[('Content-Type','application/pdf'),
            ('Content-Disposition','attachment; filename="%s.pdf"' % (secure_filename(doc.name) or 'liquidacion')),
            ('Cache-Control','private, no-store')])
