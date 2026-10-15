"""PWA shell and durable, idempotent upload API for authenticated guide users."""
import json
import hashlib
import base64
import math
from werkzeug.utils import secure_filename
from .portal import MB, MAX_IMAGE, MAX_VIDEO, MAX_TOTAL, MAX_FILES, sniff_mime, IMAGE_MIMES, VIDEO_MIMES
import re
from pathlib import Path

from odoo import http, _
from odoo.exceptions import UserError, ValidationError
from odoo.http import request
from .portal import TranscashPortal

UUID_RE = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$', re.I)


def _json_reply(obj, status=200):
    return request.make_response(
        json.dumps(obj, ensure_ascii=False),
        headers=[('Content-Type', 'application/json; charset=utf-8'),
                 ('Cache-Control', 'no-store'), ('X-Content-Type-Options', 'nosniff')],
        status=status,
    )


CHUNK_SIZE = 1024 * 1024  # 1 MiB; bytes already received are NOT sent again.


class TranscashPWA(http.Controller):
    # Delegate permission and media validation to exactly the same logic as the
    # regular portal, without re-registering its routes through subclassing.
    def _guide(self, guide_id):
        return TranscashPortal()._guide(guide_id)

    def _uploaded_files(self):
        return TranscashPortal()._uploaded_files()

    @http.route('/transcash/sw.js', type='http', auth='public', website=False, methods=['GET'], csrf=False)
    def service_worker(self, **kwargs):
        # Same-origin script located under /transcash/: no Service-Worker-Allowed header needed.
        content = (Path(__file__).resolve().parents[1] / 'static/src/js/sw.js').read_bytes()
        return request.make_response(content, headers=[
            ('Content-Type', 'application/javascript; charset=utf-8'),
            ('Cache-Control', 'no-cache, no-store, must-revalidate'),
            ('X-Content-Type-Options', 'nosniff')])

    @http.route('/transcash/manifest.webmanifest', type='http', auth='public', website=False,
                methods=['GET'], csrf=False)
    def pwa_manifest(self, **kwargs):
        content = (Path(__file__).resolve().parents[1] / 'static/manifest.webmanifest').read_bytes()
        return request.make_response(content, headers=[
            ('Content-Type', 'application/manifest+json; charset=utf-8'),
            ('Cache-Control', 'public, max-age=3600'),
            ('X-Content-Type-Options', 'nosniff')])

    @http.route('/transcash/offline', type='http', auth='public', website=False, methods=['GET'], csrf=False)
    def offline_shell(self, **kwargs):
        # Never cache a page containing user, customer, guide, or CSRF data.
        content = (Path(__file__).resolve().parents[1] / 'static/offline.html').read_bytes()
        return request.make_response(content, headers=[
            ('Content-Type', 'text/html; charset=utf-8'),
            ('Cache-Control', 'no-cache'),
            ('X-Content-Type-Options', 'nosniff'),
            ('Referrer-Policy', 'same-origin'),
            ('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' blob: data:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")])

    @http.route('/transcash/sync/session', type='http', auth='user', website=False,
                methods=['GET'], csrf=False)
    def mobile_session(self, **kwargs):
        return _json_reply({
            'ok': True,
            'user_id': request.env.user.id,
            'csrf_token': request.csrf_token(time_limit=None),
        })

    def _can_stage(self, guia, kind):
        user = request.env.user
        if guia.aprobacion_global == 'aprobada':
            return False
        if kind == 'rotura':
            if (guia.chofer_usuario_id == user and user.has_group('logistica_transcash.group_transcash_chofer')) or guia._is_seller(user):
                return guia.state in ('embarque','embarcada','ruta','destino','revision')
            return guia._is_recipient(user) and guia.state in ('destino','revision','entregada')
        if kind == 'evidencia':
            if guia.chofer_usuario_id == user and user.has_group('logistica_transcash.group_transcash_chofer'):
                return guia.state in ('embarque','embarcada','ruta','destino','revision')
            return guia._is_recipient(user) and guia.state in ('destino','revision','entregada')
        return False

    def _upload_args(self, data, require_chunk=False):
        try:
            uuid = (data.get('client_uuid') or '').strip()
            guide_id = int(data.get('guide_id'))
            file_index = int(data.get('file_index'))
            file_count = int(data.get('file_count'))
            file_size = int(data.get('file_size'))
            total = int(data.get('total_chunks'))
        except (ValueError, TypeError):
            raise ValidationError(_('Metadatos del archivo incompletos.'))
        if not UUID_RE.fullmatch(uuid) or not (0 <= file_index < file_count <= MAX_FILES):
            raise ValidationError(_('Índice o identificador de archivo inválido.'))
        if not (0 < file_size <= MAX_VIDEO) or total != math.ceil(file_size / CHUNK_SIZE):
            raise ValidationError(_('Tamaño o número de bloques incorrecto.'))
        digest = (data.get('file_sha256') or '').lower().strip()
        if not re.fullmatch(r'[a-f0-9]{64}', digest):
            raise ValidationError(_('Firma SHA-256 faltante o inválida.'))
        kind = (data.get('kind') or '').strip()
        guia = self._guide(guide_id)
        if not guia or (require_chunk and not self._can_stage(guia, kind)):
            raise UserError(_('No tiene permiso para subir archivos a esta guía y etapa.'))
        filename = secure_filename(data.get('file_name') or '')[:160]
        if not filename: filename = 'archivo'
        mime = (data.get('file_mime') or '').strip()[:100]
        return uuid, guia, kind, file_index, file_count, file_size, total, digest, filename, mime

    @http.route('/transcash/sync/chunk/status', type='http', auth='user', website=False,
                methods=['GET'], csrf=False)
    def status(self, **data):
        try:
            uuid, guia, kind, index, count, size, total, digest, name, mime = self._upload_args(data)
            completed = request.env['transcash.sync.operacion'].sudo().search([('client_uuid','=',uuid)],limit=1)
            if completed:
                if completed.usuario_id != request.env.user or completed.guia_id != guia or completed.tipo != kind:
                    return _json_reply({'ok':False,'error':'Identificador de otra operación.'},409)
                return _json_reply({'ok':True,'complete':True,'received':[]})
            if not self._can_stage(guia, kind):
                return _json_reply({'ok':False,'error':'La guía ya no admite nuevos archivos.'},403)
            session = request.env['transcash.upload.sesion'].sudo().search([
                ('client_uuid','=',uuid),('file_index','=',index)],limit=1)
            if session:
                if (session.usuario_id != request.env.user or session.guia_id != guia or
                    (session.file_size,session.file_count,session.file_sha256,session.total_chunks,session.file_name) !=
                    (size,count,digest,total,name)):
                    return _json_reply({'ok':False,'error':'Metadatos de sesión incompatibles.'},409)
                return _json_reply({'ok':True,'received':[c.chunk_index for c in session.chunk_ids]})
            return _json_reply({'ok':True,'received':[]})
        except (ValidationError,UserError) as ex:
            return _json_reply({'ok':False,'error':str(ex)},422)

    @http.route('/transcash/sync/chunk/part', type='http', auth='user', website=False,
                methods=['POST'], csrf=True)
    def part(self, **data):
        try:
            uuid, guia, kind, index, count, size, total, digest, name, mime = self._upload_args(data,True)
            part_index = int(data.get('chunk_index'))
            if not 0 <= part_index < total:
                raise ValidationError(_('Bloque fuera de rango.'))
            upload = request.httprequest.files.get('chunk')
            if not upload:
                raise ValidationError(_('No se recibió el bloque.'))
            content = upload.read(CHUNK_SIZE + 1)
            expected = min(CHUNK_SIZE, size - part_index*CHUNK_SIZE)
            if len(content) != expected:
                raise ValidationError(_('Tamaño de bloque incorrecto.'))
            checksum = hashlib.sha256(content).hexdigest()
            cr = request.env.cr
            # Transaction-level advisory lock avoids duplicate sessions/chunks
            # across browser tabs and concurrent sync workers.
            cr.execute('SELECT pg_advisory_xact_lock(hashtext(%s))', (uuid + ':' + str(index),))
            Session = request.env['transcash.upload.sesion'].sudo()
            session = Session.search([('client_uuid','=',uuid),('file_index','=',index)],limit=1)
            if session:
                if (session.usuario_id != request.env.user or session.guia_id != guia or
                    session.file_size != size or session.file_count != count or
                    session.file_sha256 != digest or session.total_chunks != total or
                    session.file_name != name):
                    return _json_reply({'ok':False,'error':'No se permite reutilizar un archivo con otros metadatos.'},409)
            else:
                # Cap per-user staged media to avoid filling the server with
                # abandoned resumable uploads. Device retains unsent originals.
                staged = Session.search([('usuario_id','=',request.env.user.id)], limit=101)
                if len(staged) > 100 or sum(staged.mapped('file_size')) + size > 250 * MB:
                    return _json_reply({'ok':False,'error':'Límite de 250 MB en videos temporales. Sincronice o solicite limpieza.'},413)
                session = Session.create({'client_uuid':uuid,'file_index':index,
                    'file_count':count,'file_size':size,'file_sha256':digest,
                    'file_name':name,'file_mime':mime,'total_chunks':total,
                    'guia_id':guia.id,'usuario_id':request.env.user.id})
            old = session.chunk_ids.filtered(lambda c:c.chunk_index == part_index)[:1]
            if old:
                if old.sha256 != checksum or old.byte_count != len(content):
                    return _json_reply({'ok':False,'error':'Bloque ya almacenado con diferente contenido.'},409)
                return _json_reply({'ok':True,'duplicate':True,'chunk_index':part_index})
            request.env['transcash.upload.parte'].sudo().create({
                'sesion_id':session.id, 'chunk_index':part_index, 'byte_count':len(content),
                'sha256':checksum, 'payload':base64.b64encode(content)})
            # Update session write_date for retention calculation
            session.write({'file_mime':mime})
            return _json_reply({'ok':True,'chunk_index':part_index})
        except (ValidationError,UserError,ValueError,TypeError) as ex:
            return _json_reply({'ok':False,'error':str(ex)},422)

    def _join_staged_files(self, uuid, guia, count):
        if not 0 <= count <= MAX_FILES:
            raise ValidationError(_('Número de archivos inválido.'))
        sessions = request.env['transcash.upload.sesion'].sudo().search(
            [('client_uuid','=',uuid),('guia_id','=',guia.id),('usuario_id','=',request.env.user.id)])
        if len(sessions) != count:
            raise ValidationError(_('Faltan archivos pendientes de cargar.'))
        files = []
        total_size = 0
        for i in range(count):
            session = sessions.filtered(lambda s:s.file_index==i)[:1]
            if not session: raise ValidationError(_('Falta el archivo %d.') % (i+1))
            raw = session.joined_binary()
            actual = sniff_mime(raw)
            if actual not in IMAGE_MIMES + VIDEO_MIMES:
                raise ValidationError(_('Archivo no reconocido por su contenido.'))
            if actual in IMAGE_MIMES and len(raw) > MAX_IMAGE:
                raise ValidationError(_('Fotografía demasiado grande.'))
            if actual in VIDEO_MIMES and len(raw) > MAX_VIDEO:
                raise ValidationError(_('Video demasiado grande.'))
            total_size += len(raw)
            if total_size > MAX_TOTAL:
                raise ValidationError(_('El conjunto supera 110 MB.'))
            files.append((base64.b64encode(raw).decode('ascii'),session.file_name,actual))
        return files, sessions

    @http.route('/transcash/sync/upload', type='http', auth='user', website=False,
                methods=['POST'], csrf=True)
    def upload(self, **post):
        uuid = (post.get('client_uuid') or '').strip()
        if not UUID_RE.fullmatch(uuid):
            return _json_reply({'ok': False, 'error': 'Identificador de sincronización inválido.'}, 422)
        try:
            guide_id = int(post.get('guide_id') or 0)
        except (TypeError, ValueError):
            return _json_reply({'ok': False, 'error': 'Identificador de guía inválido.'}, 422)
        guia = self._guide(guide_id)
        if not guia:
            return _json_reply({'ok': False, 'error': 'Esta guía ya no está disponible para el usuario.'}, 403)
        kind = (post.get('kind') or '').strip()
        if not self._can_stage(guia, kind):
            return _json_reply({'ok': False, 'error': 'No autorizado para esta guía o etapa.'}, 403)
        if kind not in ('evidencia', 'rotura'):
            return _json_reply({'ok': False, 'error': 'Tipo de registro no permitido.'}, 422)
        captured_at = (post.get('captured_at') or '').strip()
        if captured_at and not re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z', captured_at):
            return _json_reply({'ok': False, 'error': 'Fecha de captura no válida.'}, 422)
        operation_model = request.env['transcash.sync.operacion'].sudo()
        try:
            # Serialize requests with the same UUID even across phones/service workers.
            request.env.cr.execute('SELECT pg_advisory_xact_lock(hashtext(%s))', (uuid,))
            previous = operation_model.search([('client_uuid', '=', uuid)], limit=1)
            if previous:
                if previous.usuario_id.id != request.env.user.id or previous.guia_id != guia or previous.tipo != kind:
                    return _json_reply({'ok': False, 'error': 'El identificador ya pertenece a otra operación.'}, 409)
                return _json_reply({'ok': True, 'duplicate': True, 'id': previous.registro_id})
            # On validation errors restore all mutations, including files and log rows.
            with request.env.cr.savepoint():
                if post.get('chunked') == '1':
                    try: file_count = int(post.get('file_count'))
                    except (TypeError,ValueError): raise ValidationError(_('file_count inválido.'))
                    files, sessions = self._join_staged_files(uuid, guia, file_count)
                else:
                    files = self._uploaded_files()
                    sessions = request.env['transcash.upload.sesion'].sudo().browse()
                if kind == 'rotura':
                    line_id = int(post.get('linea_id') or '0')
                    line = guia.linea_ids.filtered(lambda l: l.id == line_id and l.vigente_erp)[:1]
                    r = request.env['transcash.rotura'].register_damage(
                        guia, line, post.get('cantidad_rota'), post.get('observacion') or '', files)
                    record_id = r.id
                    r.sudo().write({'fecha_captura_dispositivo': captured_at or False})
                else:
                    tipo = (post.get('tipo') or '').strip()
                    novelty = (post.get('tipo_novedad') or 'ninguna').strip()
                    if novelty == 'rotura':
                        raise UserError(_('Reporta roturas por producto, no como novedad general.'))
                    if tipo in ('carga', 'llegada') and not files:
                        raise UserError(_('Debe adjuntar una fotografía o video.'))
                    record_id = False
                    for content, filename, mime in (files or [(False, False, False)]):
                        ev = request.env['transcash.evidencia'].register_evidence(
                            guia, tipo, post.get('observacion') or '', content, filename, mime, novelty)
                        ev.sudo().write({'fecha_captura_dispositivo': captured_at or False})
                        if not record_id:
                            record_id = ev.id
                operation_model.create({
                    'client_uuid': uuid, 'guia_id': guia.id, 'usuario_id': request.env.user.id,
                    'tipo': kind, 'registro_id': record_id or 0,
                    'fecha_captura_dispositivo': captured_at or False,
                })
                if sessions:
                    sessions.unlink()  # server ACK receipt survives a dropped response
            return _json_reply({'ok': True, 'duplicate': False, 'id': record_id})
        except (UserError, ValidationError, ValueError, TypeError) as exc:
            return _json_reply({'ok': False, 'error': str(exc)}, 422)
