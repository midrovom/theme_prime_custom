# -*- coding: utf-8 -*-
"""Transporte HTTP para las APIs existentes en ``api_administrator``.

Algunas instalaciones de api_administrator solo contienen el modelo de
configuración y no implementan ``call_api``. Este servicio admite ambas:
utiliza el método si existe, o consulta la API GET seleccionada con la misma
autenticación por cabeceras que la integración ERP existente.

No registra ni guarda contraseñas ni crea registros api.administrator.
"""
import logging
from urllib.parse import urlsplit

import requests

from odoo import api, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class ExpenseBudgetAPITransport(models.AbstractModel):
    _name = 'expense.budget.api.transport'
    _description = 'Transporte para APIs ERP existentes'

    @api.model
    def get_json(self, api_record, company):
        """Obtiene JSON utilizando la API seleccionada en API Administrator.

        Si el addon administrador ofrece ``call_api``, conserva su mecanismo
        de autenticación. Si no existe, hace GET con las cabeceras de ese
        addon, sin crear nuevas credenciales o configuraciones.
        """
        api_record.ensure_one()
        company.ensure_one()
        if (api_record.company_id.id != company.id or
                (api_record.type or '').lower() != 'get' or
                api_record.status != 'A'):
            raise UserError(_('La API debe ser GET, estar activa y pertenecer a la empresa.'))

        administrator = self.env['api.administrator'].sudo()
        call_api = getattr(administrator, 'call_api', None)
        if callable(call_api):
            return call_api(api_record.name, method='get', company_id=company.id)
        return self._http_get_json(api_record)

    @api.model
    def _http_get_json(self, api_record):
        """GET alternativo para instalaciones sin método ``call_api``.

        Las credenciales solo se leen desde el registro de API Administrator.
        El URL no se registra para evitar filtrar posibles secretos en query.
        """
        api_record.ensure_one()
        base = (api_record.url or '').strip()
        endpoint = (api_record.end_point or '').strip()
        # Algunas configuraciones guardan la URL absoluta en end_point.
        if urlsplit(endpoint).scheme in ('http', 'https'):
            url = endpoint
        elif base and endpoint:
            url = base.rstrip('/') + '/' + endpoint.lstrip('/')
        else:
            url = base or endpoint

        parsed = urlsplit(url)
        if parsed.scheme not in ('http', 'https') or not parsed.netloc:
            raise UserError(_(
                'La API seleccionada no tiene una URL HTTP(S) válida en API Administrator.'
            ))

        userid = (api_record.user_id or '').strip()
        password = (api_record.password or '').strip()
        if not userid or not password:
            raise UserError(_(
                'Faltan User ID o Password de la API en API Administrator.'
            ))

        headers = {
            'Accept': 'application/json',
            'version': '1',
            'framework': 'PRUEBAS',
            'userid': userid,
            'password': password,
            'deviceid': '000000000000000',
            'sessionid': '0',
        }
        try:
            response = requests.get(url, headers=headers, timeout=(15, 180))
            response.raise_for_status()
        except requests.exceptions.Timeout as exc:
            raise UserError(_(
                'Se agotó el tiempo de respuesta de la API ERP (API ID %s).'
            ) % api_record.id) from exc
        except requests.exceptions.HTTPError as exc:
            # No exponer el cuerpo de error: puede contener tokens o datos.
            status = response.status_code
            raise UserError(_(
                'La API ERP devolvió HTTP %(status)s (API ID %(api)s). '
                'Revise los datos de autenticación en API Administrator.'
            ) % {'status': status, 'api': api_record.id}) from exc
        except requests.exceptions.RequestException as exc:
            raise UserError(_(
                'No fue posible conectar con la API ERP (API ID %s). '
                'Revise la URL, red y certificado SSL.'
            ) % api_record.id) from exc

        try:
            result = response.json()
        except ValueError as exc:
            raise UserError(_(
                'La API ERP no devolvió un JSON válido (API ID %s).'
            ) % api_record.id) from exc
        _logger.info('[PRESUPUESTOS ERP] GET HTTP directo correcto: API ID %s, HTTP %s',
                     api_record.id, response.status_code)
        return result
