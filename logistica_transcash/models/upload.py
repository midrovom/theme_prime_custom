"""Server-side chunk staging for PWA; separate from finalized evidence records.
Each 1 MiB chunk lives in the Odoo filestore (Binary attachment=True), not RAM
between requests; cleanup removes abandoned uploads after 7 days.
"""
import base64
import hashlib
from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class TranscashUploadSesion(models.Model):
    _name = 'transcash.upload.sesion'
    _description = 'Video offline parcialmente subido'
    _order = 'create_date desc'

    client_uuid = fields.Char(required=True, index=True, readonly=True)
    guia_id = fields.Many2one('transcash.guia', required=True, ondelete='cascade', readonly=True)
    usuario_id = fields.Many2one('res.users', required=True, ondelete='cascade', readonly=True)
    file_index = fields.Integer(required=True, readonly=True)
    file_count = fields.Integer(required=True, readonly=True)
    file_name = fields.Char(required=True, readonly=True)
    file_size = fields.Integer(required=True, readonly=True)
    file_sha256 = fields.Char(required=True, readonly=True)
    file_mime = fields.Char(readonly=True)
    total_chunks = fields.Integer(required=True, readonly=True)
    chunk_ids = fields.One2many('transcash.upload.parte', 'sesion_id', readonly=True)

    _sql_constraints = [('upload_unique', 'unique(client_uuid, file_index)',
                         'El archivo de esta operación ya tiene una sesión.')]

    @api.model
    def cron_cleanup_chunks(self):
        # Never discard a recently-progressed active upload; the next attempt
        # will restart from part zero after expiration.
        old = fields.Datetime.now() - timedelta(days=7)
        uploads = self.sudo().search([('write_date', '<', old)], limit=200)
        uploads.unlink()
        return True

    def joined_binary(self):
        self.ensure_one()
        chunks = self.chunk_ids.sorted('chunk_index')
        if len(chunks) != self.total_chunks or [x.chunk_index for x in chunks] != list(range(self.total_chunks)):
            raise UserError(_('Este video todavía tiene bloques por enviar.'))
        data = bytearray()
        for part in chunks:
            raw = base64.b64decode(part.payload)
            if len(raw) != part.byte_count or hashlib.sha256(raw).hexdigest() != part.sha256:
                raise UserError(_('Un bloque de video no supera la verificación.'))
            data.extend(raw)
        if len(data) != self.file_size or hashlib.sha256(data).hexdigest() != self.file_sha256:
            raise UserError(_('El archivo completo no coincide con su firma SHA-256.'))
        return bytes(data)


class TranscashUploadParte(models.Model):
    _name = 'transcash.upload.parte'
    _description = 'Bloque persistido de evidencia móvil'
    _order = 'chunk_index'

    sesion_id = fields.Many2one('transcash.upload.sesion', required=True, index=True, ondelete='cascade')
    chunk_index = fields.Integer(required=True, readonly=True)
    byte_count = fields.Integer(required=True, readonly=True)
    sha256 = fields.Char(required=True, readonly=True)
    payload = fields.Binary(attachment=True, required=True, readonly=True)

    _sql_constraints = [('chunk_unique', 'unique(sesion_id, chunk_index)',
                         'Este bloque ya fue subido.')]
