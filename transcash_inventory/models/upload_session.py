# -*- coding: utf-8 -*-
"""Almacenamiento temporal y privado de cargas XLSX fragmentadas.

Cada bloque se recibe como solicitud HTTP independiente para evitar que un
único POST grande exceda el límite de Odoo o del proxy inverso.
"""
import base64
import logging
import secrets
from datetime import timedelta

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class TranscashInventoryUploadSession(models.Model):
    _name = 'transcash.inventory.upload.session'
    _description = 'Carga temporal XLSX de inventario Transcash'
    _order = 'create_date desc, id desc'

    upload_token = fields.Char(required=True, index=True, copy=False, default=lambda self: secrets.token_urlsafe(32))
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company, index=True)
    user_id = fields.Many2one('res.users', required=True, default=lambda self: self.env.user, index=True)
    filename = fields.Char(required=True)
    expected_size = fields.Integer(required=True)
    total_chunks = fields.Integer(required=True)
    received_chunks = fields.Integer(default=0, required=True)

    def _chunk_domain(self):
        self.ensure_one()
        return [('res_model', '=', self._name), ('res_id', '=', self.id), ('name', 'like', 'transcash_part_')]

    def _get_chunks(self):
        self.ensure_one()
        return self.env['ir.attachment'].sudo().search(self._chunk_domain(), order='name asc, id asc')

    def cleanup(self):
        for item in self:
            item._get_chunks().unlink()
        self.unlink()

    @api.model
    def cleanup_expired(self):
        """Called by ir.cron; remove abandoned uploads without exposing files."""
        cutoff = fields.Datetime.now() - timedelta(hours=24)
        expired = self.sudo().search([('create_date', '<', cutoff)], limit=100)
        if expired:
            _logger.info('Transcash: limpiando %s sesiones de carga temporales', len(expired))
            expired.cleanup()
