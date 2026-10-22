# -*- coding: utf-8 -*-
"""Inventory API transport using the existing API Administrator configuration.

API Administrator owns url/end_point/user_id/password. This extension is intentionally
separate from the commission bridge; no changes to that addon are necessary.
"""
import logging
from urllib.parse import urlsplit

import requests

from odoo import models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class APIAdministrator(models.Model):
    _inherit = 'api.administrator'

    def call_inventory_api(self, timeout=120):
        """GET JSON from this configured endpoint with the existing header convention.

        Credentials never leave the server or appear in a user-facing error.
        Uses the same conventions as transcash_commission_api_bridge.
        """
        self.ensure_one()
        if self.company_id != self.env.company:
            raise UserError(_('La API seleccionada no corresponde a la empresa activa.'))
        if self.type != 'get' or self.status != 'A':
            raise UserError(_('La API de inventario debe estar activa y ser tipo GET.'))

        base_url = (self.url or '').strip()
        endpoint = (self.end_point or '').strip()
        full_url = '%s/%s' % (base_url.rstrip('/'), endpoint.lstrip('/')) if endpoint else base_url
        parsed = urlsplit(full_url)
        if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username or parsed.password:
            raise UserError(_('La API tiene una URL HTTP/HTTPS no válida. Revise API Administrator.'))
        user_id = (self.user_id or '').strip()
        password = (self.password or '').strip()
        if not user_id or not password:
            raise UserError(_('La API de inventario no tiene User ID y Password configurados.'))

        headers = {
            'Accept': 'application/json',
            'version': '1',
            'framework': 'PRUEBAS',
            'userid': user_id,
            'password': password,
            'deviceid': '000000000000000',
            'sessionid': '0',
        }
        _logger.info('Solicitando API de inventario %s, empresa %s', self.name, self.company_id.id)
        try:
            # Credentials are custom headers: never forward them through an HTTP redirect.
            response = requests.get(full_url, headers=headers, timeout=(10, timeout), allow_redirects=False)
            if response.status_code in (301, 302, 303, 307, 308):
                raise UserError(_('La API redirecciona. Configure su URL final en API Administrator.'))
            response.raise_for_status()
        except requests.Timeout as exc:
            _logger.warning('Timeout API inventario %s, empresa %s', self.name, self.company_id.id)
            raise UserError(_('La API de inventario excedió el tiempo de espera.')) from exc
        except requests.RequestException as exc:
            _logger.warning('Petición fallida API inventario %s, empresa %s: %s',
                            self.name, self.company_id.id, type(exc).__name__)
            raise UserError(_('No fue posible consultar la API de inventario. Revise conexión y credenciales en API Administrator.')) from exc
        try:
            result = response.json()
        except ValueError as exc:
            raise UserError(_('La API de inventario no devolvió JSON válido.')) from exc
        if not isinstance(result, (dict, list)):
            raise UserError(_('La respuesta de la API debe ser un objeto o una lista JSON.'))
        return result
