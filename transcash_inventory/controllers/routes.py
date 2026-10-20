# -*- coding: utf-8 -*-
import html
import base64
import zipfile
import xml.etree.ElementTree as ET
import json
import hashlib
import hmac
import secrets
import time
from pathlib import Path
from urllib.parse import quote
from odoo import http, fields
from odoo.http import request
from ..services.processor import read_xlsx, InventoryImportError, MAX_FILE
from ..services.ai_client import plan_question, planner_context, narrate_result, AIServiceError
from ..services.ai_sql import execute_sql_plan
from ..services.ai_catalog_filters import resolve_catalog_filters
from ..services.ai_schema import schema_context
from ..services.ai_export import build_result_xlsx
from ..services.ai_config_store import read_ai_settings, public_ai_settings, save_ai_settings
from odoo.exceptions import UserError
import logging
from datetime import datetime

_HTML = Path(__file__).resolve().parents[1] / 'static' / 'src' / 'dashboard.html'
_AI_CONFIG_HTML = Path(__file__).resolve().parents[1] / 'static' / 'src' / 'ai_config.html'


class TranscashDashboardController(http.Controller):
    def _can_view(self):
        user = request.env.user
        return user.has_group('transcash_inventory.group_transcash_user') or user.has_group('base.group_system')

    def _can_ai(self):
        return self._can_view() and (request.env.user.has_group('transcash_inventory.group_transcash_ai') or request.env.user.has_group('base.group_system'))

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

    def _narration_secret(self):
        """Stable server-side HMAC secret; never exposed to the browser."""
        params = request.env['ir.config_parameter'].sudo()
        secret = params.get_param('transcash_inventory.ai_signing_secret')
        if not secret:
            # Stored within the DB so tokens survive multiple Odoo workers.
            secret = secrets.token_hex(32)
            params.set_param('transcash_inventory.ai_signing_secret', secret)
        return secret.encode('utf-8')

    def _sign_narration(self, question, result, expiry):
        canonical = json.dumps({'question': question, 'result': result,
            'expiry': int(expiry), 'user': request.env.user.id,
            'company': request.env.company.id}, ensure_ascii=False,
            sort_keys=True, separators=(',', ':'), allow_nan=False)
        return hmac.new(self._narration_secret(), canonical.encode('utf-8'),
                        hashlib.sha256).hexdigest()

    @http.route('/transcash_inventory/dashboard', type='http', auth='user', methods=['GET'])
    def dashboard(self, **kw):
        if not self._can_view():
            return request.make_response('Sin permisos para Inventario Inteligente.', status=403)
        source = _HTML.read_text(encoding='utf-8')
        source = source.replace('@@CSRF@@', html.escape(request.csrf_token(), quote=True))
        source = source.replace('@@CAN_UPLOAD@@', 'true' if self._can_upload() else 'false')
        source = source.replace('@@CAN_AI@@', 'true' if self._can_ai() else 'false')
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

    def _can_configure_ai(self):
        return request.env.user.has_group('base.group_system')

    @http.route('/transcash_inventory/ai/configuration', type='http', auth='user', methods=['GET'])
    def ai_configuration_page(self, **kw):
        if not self._can_configure_ai():
            return request.make_response('Solo el administrador puede configurar ChatGPT.', status=403)
        source = _AI_CONFIG_HTML.read_text(encoding='utf-8')
        source = source.replace('@@CSRF@@', html.escape(request.csrf_token(), quote=True))
        return request.make_response(source, headers=[
            ('Content-Type', 'text/html; charset=utf-8'),
            ('Cache-Control', 'no-store, no-cache, must-revalidate'),
            ('X-Content-Type-Options', 'nosniff'),
            ('Referrer-Policy', 'same-origin')])

    @http.route('/transcash_inventory/ai/configuration/state', type='http', auth='user', methods=['GET'])
    def ai_configuration_state(self, **kw):
        if not self._can_configure_ai():
            return self._json({'error': 'Solo un administrador puede consultar esta configuración.'}, 403)
        return self._json({'ok': True, 'config': public_ai_settings(read_ai_settings(request.env))})

    @http.route('/transcash_inventory/ai/configuration/save', type='http', auth='user', methods=['POST'], csrf=True)
    def ai_configuration_save(self, **kw):
        if not self._can_configure_ai():
            return self._json({'error': 'Solo un administrador puede guardar esta configuración.'}, 403)
        try:
            enabled_raw = str(kw.get('ai_enabled') or '0').strip().lower()
            if enabled_raw not in ('0', '1'):
                return self._json({'error': 'Activación no válida.'}, 400)
            clear_key = str(kw.get('remove_key') or '0') == '1'
            with request.env.cr.savepoint():
                config = save_ai_settings(request.env, enabled_raw == '1',
                    str(kw.get('ai_model') or ''),
                    str(kw.get('api_key_new') or ''), clear_key)
            # Verificación definitiva en una SEGUNDA petición HTTP después del commit.
            return self._json({'ok': True, 'saved': True,
                               'config': public_ai_settings(config)})
        except UserError as exc:
            return self._json({'error': str(exc)}, 400)
        except Exception:
            import logging
            logging.getLogger(__name__).exception('Transcash: error al guardar configuración IA (sin credenciales)')
            return self._json({'error': 'Error del servidor al guardar. Consulte el log de Odoo, sin compartir la clave.'}, 500)

    @http.route('/transcash_inventory/ai/configuration/test', type='http', auth='user', methods=['POST'], csrf=True)
    def ai_configuration_test(self, **kw):
        if not self._can_configure_ai():
            return self._json({'error': 'Solo un administrador puede probar la conexión.'}, 403)
        config = read_ai_settings(request.env)
        if not config['enabled'] or not config['key']:
            return self._json({'error': 'Guarde primero una configuración activa con API Key.'}, 400)
        try:
            from ..services.ai_client import call_responses
            result = call_responses(config['key'], config['model'],
                'Responde únicamente con OK.', 'Verificar conexión de OpenAI.', max_tokens=350)
            return self._json({'ok': True, 'message': 'Conexión confirmada con OpenAI: ' + result[:90]})
        except AIServiceError as exc:
            return self._json({'error': str(exc)}, 502)
        except Exception:
            import logging
            logging.getLogger(__name__).exception('Transcash: fallo al probar OpenAI (sin credenciales)')
            return self._json({'error': 'Fallo al probar la conexión. Revise el log de Odoo.'}, 502)

    @http.route('/transcash_inventory/ai/status', type='http', auth='user', methods=['GET'])
    def ai_status(self, **kw):
        if not self._can_ai():
            return self._json({'error': 'Su usuario necesita el permiso Consultas de ChatGPT.'}, 403)
        config = read_ai_settings(request.env)
        enabled = config['enabled']
        key_ok = bool(config['key'])
        model_ok = bool(config['model'])
        if not key_ok:
            message = 'API Key no guardada en Odoo. Abra Configuración de ChatGPT, ingrese la clave y guarde.'
            state = 'missing_key'
        elif not enabled:
            message = 'API Key guardada, pero ChatGPT está desactivado. Active la casilla y guarde la configuración.'
            state = 'disabled'
        elif not model_ok:
            message = 'Falta configurar el modelo de OpenAI. Revise Configuración de ChatGPT.'
            state = 'missing_model'
        else:
            message = 'ChatGPT activado y API Key guardada. Puede consultar.'
            state = 'ready'
        return self._json({'enabled': enabled and key_ok and model_ok,
                           'activated': enabled, 'configured': key_ok,
                           'model_configured': model_ok, 'state': state,
                           'message': message})

    @http.route('/transcash_inventory/ai/prepare', type='http', auth='user', methods=['POST'], csrf=True)
    def ai_prepare_relational(self, **kw):
        """Lazy migration of previously imported snapshots to normalized Odoo tables."""
        if not self._can_ai():
            return self._json({'error': 'No tiene permiso para consultar.'}, 403)
        snap_id = str(kw.get('snapshot_id') or '').strip()
        domain = [('company_id', '=', request.env.company.id)]
        if snap_id:
            if not snap_id.isdigit():
                return self._json({'error': 'Versión no válida.'}, 400)
            domain.append(('id', '=', int(snap_id)))
        snapshot = request.env['transcash.inventory.snapshot'].search(domain, order='create_date desc, id desc', limit=1)
        if not snapshot:
            return self._json({'error': 'No hay inventario importado en esta empresa.'}, 404)
        try:
            snapshot.ensure_relational_data()
            return self._json({'ok': True, 'ready': True})
        except UserError as exc:
            return self._json({'error': 'No fue posible preparar la información. Intente nuevamente.'}, 409)
        except Exception:
            import logging
            logging.getLogger(__name__).exception('Transcash: preparación de facts SQL')
            return self._json({'error': 'No fue posible preparar la información. Intente nuevamente.'}, 500)

    @http.route('/transcash_inventory/ai/schema', type='http', auth='user', methods=['GET'])
    def ai_schema_public(self, **kw):
        """Return ONLY whitelisted metadata for this module, never other Odoo tables."""
        if not self._can_configure_ai():
            return self._json({'error': 'Se requiere el permiso Consultas ChatGPT.'}, 403)
        snap_id = str(kw.get('snapshot_id') or '').strip()
        domain = [('company_id', '=', request.env.company.id)]
        if snap_id:
            if not snap_id.isdigit():
                return self._json({'error': 'Versión no válida.'}, 400)
            domain.append(('id', '=', int(snap_id)))
        snapshot = request.env['transcash.inventory.snapshot'].search(domain, order='create_date desc, id desc', limit=1)
        if not snapshot:
            return self._json({'error': 'No hay versiones del inventario.'}, 404)
        if not snapshot.relational_ready:
            return self._json({'error': 'Prepare primero las tablas de consultas SQL.'}, 409)
        return self._json({'ok': True, 'schema': schema_context(request.env, snapshot)})

    @http.route('/transcash_inventory/ai/ask', type='http', auth='user', methods=['POST'], csrf=True)
    def ai_ask(self, **kw):
        """Solo datos al usuario; trazabilidad técnica exclusiva de la bitácora."""
        if not self._can_ai():
            return self._json({'error': 'No tiene permiso para consultar.'}, 403)
        question = str(kw.get('question') or '').strip()
        if not 6 <= len(question) <= 700:
            return self._json({'error': 'Escriba una pregunta de entre 6 y 700 caracteres.'}, 400)
        config = read_ai_settings(request.env)
        if not config['enabled'] or not config['key'] or not config['model']:
            return self._json({'error': 'El asistente no está disponible. Solicite al administrador revisar la configuración.'}, 503)
        from datetime import timedelta
        since = fields.Datetime.now() - timedelta(hours=1)
        audit_model = request.env['transcash.inventory.ai.request'].sudo()
        domain_limit = [('user_id', '=', request.env.user.id),
                        ('create_date', '>=', fields.Datetime.to_string(since))]
        if audit_model.search_count(domain_limit) >= 25:
            return self._json({'error': 'Ha alcanzado el límite de consultas por hora. Intente más tarde.'}, 429)
        started = time.monotonic()
        audit = None
        try:
            snap_id = str(kw.get('snapshot_id') or '').strip()
            snapshot_domain = [('company_id', '=', request.env.company.id)]
            if snap_id:
                if not snap_id.isdigit():
                    return self._json({'error': 'Versión no válida.'}, 400)
                snapshot_domain.append(('id', '=', int(snap_id)))
            snapshot = request.env['transcash.inventory.snapshot'].search(
                snapshot_domain, order='create_date desc, id desc', limit=1)
            if not snapshot:
                return self._json({'error': 'No hay información disponible para consultar.'}, 404)
            # The browser never sees a SQL statement or database diagnostics.
            with request.env.cr.savepoint():
                snapshot.ensure_relational_data()
            available = json.loads(snapshot.relational_months or '[]')
            if not available:
                return self._json({'error': 'No se encontraron períodos disponibles.'}, 400)
            default_end = str(kw.get('hasta') or available[-1])
            default_start = str(kw.get('desde') or available[max(0, len(available)-12)])
            if default_start not in available or default_end not in available:
                return self._json({'error': 'Seleccione un período disponible.'}, 400)
            request.env.cr.execute('SELECT pg_try_advisory_xact_lock(%s, %s)',
                                   [82318, request.env.user.id])
            if not request.env.cr.fetchone()[0]:
                return self._json({'error': 'Ya tiene otra consulta en proceso. Espere a que termine.'}, 409)
            if audit_model.search_count(domain_limit) >= 25:
                return self._json({'error': 'Ha alcanzado el límite de consultas por hora.'}, 429)
            audit = audit_model.create({
                'user_id': request.env.user.id, 'company_id': request.env.company.id,
                'snapshot_id': snapshot.id, 'question': question, 'state': 'started',
            })
            ui = {'categoria': str(kw.get('categoria') or '')[:120],
                  'marca': str(kw.get('marca') or '')[:120],
                  'formato': str(kw.get('formato') or '')[:120],
                  'proveedor': str(kw.get('proveedor') or '')[:120]}
            with request.env.cr.savepoint():
                plan = plan_question(config['key'], config['model'], question,
                    available, default_start, default_end, ui,
                    schema_context(request.env, snapshot))
                plan = resolve_catalog_filters(request.env, snapshot, plan, question, ui)
                if plan.get('metric') == 'no_disponible':
                    audit.write({
                        'state': 'unavailable', 'plan_json': json.dumps(plan, ensure_ascii=False),
                        'error_detail': str(plan.get('razon') or '')[:2000],
                        'duration_ms': int((time.monotonic()-started)*1000),
                        'finished_at': fields.Datetime.now(),
                    })
                    return self._json({'ok': True, 'available': False,
                        'message': 'No es posible calcular ese indicador con la información disponible.'})
                data = execute_sql_plan(request.env, snapshot, plan,
                                        default_start, default_end)
            # Technical details persist exclusively in the administrator log.
            sql = str(data.pop('sql_consulta', '') or '')
            sql_params = data.pop('sql_parametros', [])
            data.pop('fuente', None)
            data.pop('observaciones', None)
            record_data = {
                'state': 'done', 'dimension': str(data.get('dimension') or '')[:100],
                'metrics': ', '.join(data.get('metricas') or [])[:255],
                'row_count': len(data.get('filas') or []),
                'duration_ms': int((time.monotonic()-started)*1000),
                'finished_at': fields.Datetime.now(),
                'sql_query': sql,
                'sql_parameters': json.dumps(sql_params, ensure_ascii=False, default=str),
                'plan_json': json.dumps(plan, ensure_ascii=False, default=str),
                'result_json': json.dumps(data, ensure_ascii=False, allow_nan=False),
            }
            audit.write(record_data)
            return self._json({'ok': True, 'available': True,
                               'result': data, 'request_id': audit.id})
        except (AIServiceError, ValueError, KeyError, TypeError) as exc:
            if audit:
                audit.write({'state': 'failed', 'error_detail': str(exc)[:2000],
                    'duration_ms': int((time.monotonic()-started)*1000),
                    'finished_at': fields.Datetime.now()})
            return self._json({'error': 'No se pudo completar el análisis. Revise su pregunta y los filtros.'}, 400)
        except Exception as exc:
            logging.getLogger(__name__).exception('Transcash: error de análisis IA')
            if audit:
                audit.write({'state': 'failed', 'error_detail': str(exc)[:2000],
                    'duration_ms': int((time.monotonic()-started)*1000),
                    'finished_at': fields.Datetime.now()})
            return self._json({'error': 'No fue posible completar el análisis. Intente nuevamente.'}, 500)

    @http.route('/transcash_inventory/ai/export_xlsx', type='http', auth='user', methods=['POST'], csrf=True)
    def ai_export_xlsx(self, **kw):
        """Exportar únicamente la propia consulta validada y guardada en Odoo."""
        if not self._can_ai():
            return self._json({'error': 'No tiene permiso para exportar consultas.'}, 403)
        raw_id = str(kw.get('request_id') or '').strip()
        if not raw_id.isdigit():
            return self._json({'error': 'El resultado seleccionado no está disponible.'}, 400)
        # Elevated read is bounded by an explicit owner/company/state check.
        log = request.env['transcash.inventory.ai.request'].sudo().search([
            ('id', '=', int(raw_id)), ('user_id', '=', request.env.user.id),
            ('company_id', '=', request.env.company.id), ('state', '=', 'done')
        ], limit=1)
        if not log or not log.result_json:
            return self._json({'error': 'El resultado ya no está disponible. Realice la consulta de nuevo.'}, 404)
        try:
            result = json.loads(log.result_json)
            content = build_result_xlsx(result, log.question or '', created=fields.Datetime.now())
            log.write({'export_count': log.export_count + 1,
                       'last_export_at': fields.Datetime.now()})
        except Exception:
            logging.getLogger(__name__).exception('Transcash: fallo exportando resultados Excel')
            return self._json({'error': 'No se pudo generar el archivo Excel.'}, 500)
        filename = 'Transcash_Consulta_%s.xlsx' % fields.Datetime.now().strftime('%Y%m%d_%H%M%S')
        return request.make_response(content, headers=[
            ('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
            ('Content-Disposition', 'attachment; filename="%s"' % filename),
            ('Cache-Control', 'private, no-store'),
            ('X-Content-Type-Options', 'nosniff'),
        ])

    @http.route('/transcash_inventory/ai/explain', type='http', auth='user', methods=['POST'], csrf=True)
    def ai_explain(self, **kw):
        # Retained as a compatibility endpoint but explanations are disabled.
        return self._json({'error': 'Esta función ya no está disponible.'}, 410)

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

    # --- Importación robusta Odoo 18: carga por bloques en un menú independiente ---
    @http.route('/transcash_inventory/import', type='http', auth='user', methods=['GET'])
    def import_page(self, **kw):
        if not self._can_upload():
            return request.make_response('No tiene permisos para cargar archivos de inventario.', status=403)
        source = (Path(__file__).resolve().parents[1] / 'static' / 'src' / 'upload.html').read_text(encoding='utf-8')
        source = source.replace('@@CSRF@@', html.escape(request.csrf_token(), quote=True))
        source = source.replace('@@COMPANY@@', html.escape(request.env.company.display_name, quote=True))
        return request.make_response(source, headers=[('Content-Type', 'text/html; charset=utf-8'),
            ('Cache-Control', 'no-store'), ('X-Content-Type-Options', 'nosniff')])

    def _find_upload(self, token):
        if not isinstance(token, str) or not 24 <= len(token) <= 128:
            return None
        return request.env['transcash.inventory.upload.session'].search([
            ('upload_token', '=', token),
            ('user_id', '=', request.env.user.id),
            ('company_id', '=', request.env.company.id),
        ], limit=1)

    @http.route('/transcash_inventory/upload/start', type='http', auth='user', methods=['POST'], csrf=True)
    def start_upload(self, **kw):
        if not self._can_upload():
            return self._json({'error': 'No tiene permisos para importar.'}, 403)
        try:
            name = str(kw.get('filename') or '').replace('\\', '/').split('/')[-1].strip()
            size = int(kw.get('size') or 0)
            parts = int(kw.get('parts') or 0)
            chunk_size = 384 * 1024
            if not name or len(name) > 180 or not name.lower().endswith('.xlsx'):
                return self._json({'error': 'Seleccione un archivo Excel .xlsx válido.'}, 400)
            if size < 1 or size > MAX_FILE:
                return self._json({'error': 'El Excel está vacío o supera los 45 MB permitidos.'}, 400)
            if parts != (size + chunk_size - 1) // chunk_size:
                return self._json({'error': 'El número de fragmentos del Excel es incorrecto.'}, 400)
            rec = request.env['transcash.inventory.upload.session'].create({
                'filename': name, 'expected_size': size, 'total_chunks': parts,
                'user_id': request.env.user.id, 'company_id': request.env.company.id,
            })
            return self._json({'ok': True, 'token': rec.upload_token, 'chunk_size': chunk_size, 'parts': parts})
        except (TypeError, ValueError, OverflowError):
            return self._json({'error': 'Los datos del archivo no son válidos.'}, 400)

    @http.route('/transcash_inventory/upload/chunk', type='http', auth='user', methods=['POST'], csrf=True)
    def upload_chunk(self, **kw):
        if not self._can_upload():
            return self._json({'error': 'No tiene permisos para importar.'}, 403)
        upload = self._find_upload(kw.get('token'))
        if not upload:
            return self._json({'error': 'Sesión de carga no encontrada o caducada. Vuelva a seleccionar el archivo.'}, 404)
        try:
            index = int(kw.get('index') or 0)
        except (TypeError, ValueError):
            return self._json({'error': 'Fragmento no válido.'}, 400)
        if index != upload.received_chunks or index < 0 or index >= upload.total_chunks:
            return self._json({'error': 'Fragmentos fuera de orden. Reintente la carga desde el principio.'}, 409)
        file = request.httprequest.files.get('chunk')
        if file is None:
            return self._json({'error': 'No se recibió el contenido de este fragmento.'}, 400)
        chunk_size = 384 * 1024
        expected = min(chunk_size, upload.expected_size - index * chunk_size)
        payload = file.stream.read(chunk_size + 1)
        if len(payload) != expected:
            return self._json({'error': 'Fragmento incompleto: se esperaban %s bytes y llegaron %s.' % (expected, len(payload))}, 400)
        request.env['ir.attachment'].sudo().create({
            'name': 'transcash_part_%04d' % index,
            'res_model': 'transcash.inventory.upload.session',
            'res_id': upload.id,
            'type': 'binary', 'mimetype': 'application/octet-stream',
            'public': False, 'datas': base64.b64encode(payload).decode('ascii'),
        })
        upload.write({'received_chunks': index + 1})
        return self._json({'ok': True, 'received': upload.received_chunks, 'total': upload.total_chunks})

    @http.route('/transcash_inventory/upload/finish', type='http', auth='user', methods=['POST'], csrf=True)
    def finish_upload(self, **kw):
        if not self._can_upload():
            return self._json({'error': 'No tiene permisos para importar.'}, 403)
        upload = self._find_upload(kw.get('token'))
        if not upload:
            return self._json({'error': 'Sesión no encontrada. Vuelva a iniciar la carga.'}, 404)
        if upload.received_chunks != upload.total_chunks:
            return self._json({'error': 'La transferencia no terminó: %s de %s fragmentos.' % (
                upload.received_chunks, upload.total_chunks)}, 409)
        try:
            blocks = upload._get_chunks()
            if len(blocks) != upload.total_chunks:
                return self._json({'error': 'Faltan fragmentos almacenados. Reinicie la carga.'}, 409)
            pieces = []
            for index, block in enumerate(blocks):
                if block.name != 'transcash_part_%04d' % index:
                    return self._json({'error': 'Los fragmentos no están ordenados correctamente.'}, 409)
                pieces.append(base64.b64decode(block.datas))
            payload = b''.join(pieces)
            if len(payload) != upload.expected_size or not payload.startswith(b'PK'):
                upload.cleanup()
                return self._json({'error': 'Archivo incompleto o no corresponde a un Excel XLSX.'}, 400)
            dataset = read_xlsx(payload)
            snapshot = request.env['transcash.inventory.snapshot'].create_from_dataset(
                dataset, filename=upload.filename, raw_size=len(payload))
            snapshot_id = snapshot.id
            upload.cleanup()
            return self._json({'ok': True, 'snapshot_id': snapshot_id,
                               'products': len(dataset['products']),
                               'period': dataset['source'].get('end'),
                               'revenue': dataset['summary'].get('ventas12', 0),
                               'stock': dataset['summary'].get('stock_catalogo', 0)})
        except (InventoryImportError, zipfile.BadZipFile, ET.ParseError, KeyError, IndexError, ValueError) as exc:
            upload.cleanup()
            return self._json({'error': 'Excel no compatible: %s' % str(exc)[:350]}, 400)
        except Exception:
            import logging
            logging.getLogger(__name__).exception('Transcash: error inesperado procesando Excel')
            return self._json({'error': 'Ocurrió un error interno al guardar el inventario. Revise el log de Odoo.'}, 500)

    @http.route('/transcash_inventory/upload/cancel', type='http', auth='user', methods=['POST'], csrf=True)
    def cancel_upload(self, **kw):
        if not self._can_upload():
            return self._json({'error': 'Sin permisos'}, 403)
        upload = self._find_upload(kw.get('token'))
        if upload:
            upload.cleanup()
        return self._json({'ok': True})

    # --- Catálogo de imágenes Transcash.ec, vinculado por SKU exacto ---
    @http.route('/transcash_inventory/photos', type='http', auth='user', methods=['GET'])
    def photos_by_skus(self, **kw):
        if not self._can_view():
            return self._json({'error': 'Sin permisos para ver imágenes'}, 403)
        try:
            codes = json.loads(kw.get('skus', '[]'))
            if not isinstance(codes, list) or len(codes) > 80 or any(not isinstance(s, str) for s in codes):
                return self._json({'error': 'Lista de SKU no válida (máximo 80)'}, 400)
            data = request.env['transcash.inventory.photo'].images_for_skus(codes)
            return self._json({'images': data})
        except (TypeError, ValueError, json.JSONDecodeError):
            return self._json({'error': 'Lista de SKU mal formada'}, 400)

    @http.route('/transcash_inventory/photos/thumb', type='http', auth='user', methods=['GET'])
    def photo_thumbnail(self, **kw):
        """Same-origin miniature avoids browser cross-site image/hotlink failures."""
        if not self._can_view():
            return request.make_response('Sin permisos', status=403)
        sku = str(kw.get('sku') or '').strip()[:120]
        photo = request.env['transcash.inventory.photo'].search([
            ('company_id', '=', request.env.company.id), ('sku', '=', sku),
            ('enabled', '=', True), ('status', '=', 'verified')], limit=1)
        if not photo or not photo.image_thumbnail:
            return request.make_response('Sin imagen verificada', status=404)
        try:
            binary = base64.b64decode(photo.image_thumbnail)
            return request.make_response(binary, headers=[
                ('Content-Type', 'image/jpeg'), ('Cache-Control', 'private, max-age=900'),
                ('X-Content-Type-Options', 'nosniff')])
        except (ValueError, TypeError):
            return request.make_response('Miniatura no disponible', status=404)

    @http.route('/transcash_inventory/photos/lookup', type='http', auth='user', methods=['GET'])
    def photo_lookup(self, **kw):
        if not self._can_view():
            return self._json({'error': 'Sin permisos'}, 403)
        sku = str(kw.get('sku') or '').strip()[:120]
        if not sku:
            return self._json({'error': 'Ingrese el SKU'}, 400)
        return self._json(request.env['transcash.inventory.photo'].images_for_skus([sku]).get(sku, {}))

    @http.route('/transcash_inventory/photos/scan', type='http', auth='user', methods=['GET'])
    def photos_sync_ui(self, **kw):
        if not self._can_upload():
            return request.make_response('No tiene permisos para sincronizar imágenes.', status=403)
        source = (Path(__file__).resolve().parents[1] / 'static' / 'src' / 'photos.html').read_text(encoding='utf-8')
        return request.make_response(source.replace('@@CSRF@@', html.escape(request.csrf_token(), quote=True)),
            headers=[('Content-Type', 'text/html; charset=utf-8'), ('Cache-Control', 'no-store')])

    @http.route('/transcash_inventory/photos/status', type='http', auth='user', methods=['GET'])
    def photos_status(self, **kw):
        if not self._can_upload():
            return self._json({'error': 'No tiene permisos'}, 403)
        sync = request.env['transcash.inventory.photo.sync'].get_current()
        snap = self._latest()
        return self._json(dict(sync.public_stats(), total_products=snap.product_count if snap else 0,
                               pages_limit=90))

    @http.route('/transcash_inventory/photos/scan', type='http', auth='user', methods=['POST'], csrf=True)
    def photos_scan(self, **kw):
        if not self._can_upload():
            return self._json({'error': 'No tiene permisos para sincronizar imágenes'}, 403)
        try:
            amount = min(4, max(1, int(kw.get('limit') or 2)))
            sync = request.env['transcash.inventory.photo.sync'].get_current()
            result = sync.scan_pages(amount)
            snap = self._latest()
            return self._json(dict(result, total_products=snap.product_count if snap else 0, pages_limit=90))
        except Exception as exc:
            from odoo.exceptions import UserError
            if isinstance(exc, UserError):
                return self._json({'error': str(exc)}, 400)
            import logging
            logging.getLogger(__name__).exception('Transcash: error en sincronización de fotos')
            return self._json({'error': 'No se pudo procesar el catálogo. Consulte el log de Odoo.'}, 500)

    @http.route('/transcash_inventory/photos/reset', type='http', auth='user', methods=['POST'], csrf=True)
    def photos_reset(self, **kw):
        if not self._can_upload():
            return self._json({'error': 'No tiene permisos'}, 403)
        if kw.get('confirm') != 'yes':
            return self._json({'error': 'Falta confirmación'}, 400)
        sync = request.env['transcash.inventory.photo.sync'].get_current()
        sync.reset_scan()
        snap = self._latest()
        return self._json(dict(sync.public_stats(), total_products=snap.product_count if snap else 0,
                               pages_limit=90))

    @http.route('/transcash_inventory/photos/queue', type='http', auth='user', methods=['POST'], csrf=True)
    def photo_queue_visible(self, **kw):
        """Enqueue visible, exact snapshot SKUs without blocking dashboard rendering."""
        if not self._can_upload():
            return self._json({'error': 'Sin permisos para buscar fotografías'}, 403)
        try:
            codes = json.loads(kw.get('skus', '[]'))
            if not isinstance(codes, list) or len(codes) > 40 or any(not isinstance(x, str) for x in codes):
                return self._json({'error': 'Lista de códigos no válida; máximo 40'}, 400)
            sync = request.env['transcash.inventory.photo.sync'].get_current()
            queued = sync.enqueue_skus(codes)
            return self._json({'ok': True, 'queued': queued})
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            return self._json({'error': 'Lista no válida: %s' % str(exc)[:100]}, 400)
        except Exception:
            import logging
            logging.getLogger(__name__).exception('Transcash: error al encolar fotos visibles')
            return self._json({'error': 'No se pudieron registrar las búsquedas'}, 500)

    @http.route('/transcash_inventory/photos/resolve', type='http', auth='user', methods=['POST'], csrf=True)
    def photo_resolve_one(self, **kw):
        """Search and validate one SKU immediately, even if catalogue pagination missed it."""
        if not self._can_upload():
            return self._json({'error': 'Sin permisos para buscar fotografías'}, 403)
        sku = str(kw.get('sku') or '').strip()[:120]
        if not sku:
            return self._json({'error': 'Ingrese un SKU'}, 400)
        supplied = str(kw.get('url') or '').strip() or None
        try:
            from odoo.exceptions import UserError
            sync = request.env['transcash.inventory.photo.sync'].get_current()
            rec = sync.resolve_single_sku(sku, supplied_url=supplied,
                                          manual=bool(supplied), force=True)
            return self._json({'ok': rec.status == 'verified', 'sku': rec.sku,
                               'status': rec.status, 'error': rec.last_error or '',
                               'image_url': ('/transcash_inventory/photos/thumb?sku=' + quote(rec.sku, safe=''))
                               if rec.status == 'verified' and rec.image_thumbnail else '',
                               'source_url': rec.image_url or '',
                               'website_url': rec.website_url or ''})
        except UserError as exc:
            return self._json({'error': str(exc)}, 400)
        except Exception:
            import logging
            logging.getLogger(__name__).exception('Transcash: búsqueda puntual fallida: %s', sku)
            return self._json({'error': 'Error inesperado buscando el SKU. Consulte el log de Odoo.'}, 500)

    @http.route('/transcash_inventory/photos/link', type='http', auth='user', methods=['POST'], csrf=True)
    def photos_link_exact(self, **kw):
        # Backward compatibility with earlier "Vincular ficha exacta" UI.
        return self.photo_resolve_one(**kw)
