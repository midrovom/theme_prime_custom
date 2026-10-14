# -*- coding: utf-8 -*-
import html
import json
from pathlib import Path
from odoo import http
from odoo.http import request
from ..services.processor import read_xlsx, InventoryImportError, MAX_FILE

_HTML = Path(__file__).resolve().parents[1] / 'static' / 'src' / 'dashboard.html'


class TranscashDashboardController(http.Controller):
    def _can_view(self):
        user = request.env.user
        return user.has_group('transcash_inventory.group_transcash_user') or user.has_group('base.group_system')

    def _can_upload(self):
        user = request.env.user
        return user.has_group('transcash_inventory.group_transcash_manager') or user.has_group('base.group_system')

    def _latest(self):
        return request.env['transcash.inventory.snapshot'].search(
            [('company_id', '=', request.env.company.id)], limit=1,
            order='create_date desc, id desc')

    def _json(self, obj, status=200):
        return request.make_response(json.dumps(obj, ensure_ascii=False),
            headers=[('Content-Type', 'application/json; charset=utf-8'),
                     ('Cache-Control', 'no-store'), ('X-Content-Type-Options', 'nosniff')],
            status=status)

    @http.route('/transcash_inventory/dashboard', type='http', auth='user', methods=['GET'])
    def dashboard(self, **kw):
        if not self._can_view():
            return request.make_response('Sin permisos para Inventario Inteligente.', status=403)
        source = _HTML.read_text(encoding='utf-8')
        source = source.replace('@@CSRF@@', html.escape(request.csrf_token(), quote=True))
        source = source.replace('@@CAN_UPLOAD@@', 'true' if self._can_upload() else 'false')
        return request.make_response(source, headers=[('Content-Type', 'text/html; charset=utf-8'),
            ('Cache-Control', 'no-store'), ('X-Content-Type-Options', 'nosniff')])

    @http.route('/transcash_inventory/data', type='http', auth='user', methods=['GET'])
    def current_data(self, **kw):
        if not self._can_view():
            return self._json({'error': 'Sin permisos'}, 403)
        snapshot_id = kw.get('snapshot_id')
        domain = [('company_id', '=', request.env.company.id)]
        if snapshot_id:
            try:
                domain.append(('id', '=', int(snapshot_id)))
            except (TypeError, ValueError):
                return self._json({'error': 'Versión no válida'}, 400)
        snapshot = request.env['transcash.inventory.snapshot'].search(domain, limit=1, order='create_date desc, id desc')
        if not snapshot:
            return self._json({'error': 'No hay importaciones. Carga el Excel desde el panel.'}, 404)
        payload = snapshot.get_dashboard_json()
        return request.make_response(payload, headers=[('Content-Type', 'application/json; charset=utf-8'),
            ('Cache-Control', 'no-store'), ('X-Content-Type-Options', 'nosniff')])

    @http.route('/transcash_inventory/upload', type='http', auth='user', methods=['POST'], csrf=True)
    def upload(self, **kw):
        if not self._can_upload():
            return self._json({'error': 'Solo el responsable de inventario puede importar archivos.'}, 403)
        file = request.httprequest.files.get('file')
        if not file or not (file.filename or '').lower().endswith('.xlsx'):
            return self._json({'error': 'Seleccione un archivo .xlsx con 4 hojas.'}, 400)
        try:
            payload = file.stream.read(MAX_FILE + 1)
            if len(payload) > MAX_FILE:
                return self._json({'error': 'Límite de carga: 45 MB'}, 413)
            dataset = read_xlsx(payload)
            snapshot = request.env['transcash.inventory.snapshot'].create_from_dataset(
                dataset, filename=file.filename[:180], raw_size=len(payload))
            return self._json({'ok': True, 'snapshot_id': snapshot.id,
                'products': len(dataset['products']), 'period': dataset['source']['end']})
        except InventoryImportError as exc:
            return self._json({'error': str(exc)}, 400)
        except (ValueError, KeyError, TypeError) as exc:
            return self._json({'error': 'Error en estructura del Excel: %s' % str(exc)[:300]}, 400)
