import logging
from urllib.parse import urlsplit, urlunsplit

import requests

from odoo import fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class APIAdministrator(models.Model):
    _inherit = "api.administrator"

    def _commission_format_date(self, value):
        date_value = fields.Date.to_date(value)
        if not date_value:
            raise UserError(_("La sincronización de comisiones requiere fecha desde y fecha hasta."))
        return date_value.strftime("%Y.%m.%d")

    def _commission_build_request_url(self, date_from, date_to):
        """Build the sales URL without altering api.administrator configuration.

        The configured ``url + end_point`` remains the source of truth. Dates are
        sent as quoted path segments, e.g.::

            /'2026.08.01'/'2026.08.31'

        If the configured endpoint contains a query string (for example the
        company parameter), the date segments are inserted in the path *before*
        that query string.

        As an optional escape hatch, ``{date_from}`` and ``{date_to}``
        placeholders can be placed directly in the configured URL/endpoint. In
        that case they are replaced in place, allowing any endpoint order without
        changing this bridge module.
        """
        self.ensure_one()
        base_url = (self.url or "").strip()
        endpoint = (self.end_point or "").strip()
        if not base_url:
            raise UserError(_("La API '%s' no tiene URL configurada.") % (self.display_name or self.name))

        if endpoint:
            full_url = "%s/%s" % (base_url.rstrip("/"), endpoint.lstrip("/"))
        else:
            full_url = base_url

        date_from_text = self._commission_format_date(date_from)
        date_to_text = self._commission_format_date(date_to)
        quoted_from = "'%s'" % date_from_text
        quoted_to = "'%s'" % date_to_text

        # Optional explicit positioning in api.administrator endpoint.
        if "{date_from}" in full_url or "{date_to}" in full_url:
            if "{date_from}" not in full_url or "{date_to}" not in full_url:
                raise UserError(_(
                    "Si usa placeholders de fecha en el endpoint debe incluir "
                    "tanto {date_from} como {date_to}."
                ))
            return full_url.replace("{date_from}", quoted_from).replace("{date_to}", quoted_to)

        parsed = urlsplit(full_url)
        path = (parsed.path or "").rstrip("/")
        path = "%s/%s/%s" % (path, quoted_from, quoted_to)
        return urlunsplit((parsed.scheme, parsed.netloc, path, parsed.query, parsed.fragment))

    def call_commission_sales_api(self, date_from, date_to, timeout=120, headers_extra=None):
        """Call this api.administrator record for commission sales.

        Authentication/header conventions intentionally mirror the existing
        Transcash API integration while keeping the change isolated in this
        bridge addon.
        """
        self.ensure_one()
        api_url = self._commission_build_request_url(date_from, date_to)
        user_id = (self.user_id or "").strip()
        password = (self.password or "").strip()

        if not user_id or not password:
            raise UserError(_(
                "Configuración incompleta para la API '%s': falta User ID o Password."
            ) % (self.display_name or self.name))

        headers = {
            "Accept": "application/json",
            "version": "1",
            "framework": "PRUEBAS",
            "userid": user_id,
            "password": password,
            "deviceid": "000000000000000",
            "sessionid": "0",
        }
        if headers_extra:
            headers.update(headers_extra)

        _logger.info(
            "Consultando API de comisiones '%s' para %s - %s",
            self.name,
            date_from,
            date_to,
        )
        try:
            response = requests.get(api_url, headers=headers, timeout=timeout)
            response.raise_for_status()
        except requests.RequestException as exc:
            _logger.exception("Error consultando API de comisiones %s", self.name)
            raise UserError(_(
                "Error consultando la API de comisiones '%(api)s': %(error)s"
            ) % {"api": self.name, "error": str(exc)}) from exc

        try:
            return response.json()
        except ValueError as exc:
            preview = (response.text or "")[:500]
            raise UserError(_(
                "La API de comisiones '%(api)s' no devolvió JSON válido. "
                "Respuesta inicial: %(preview)s"
            ) % {"api": self.name, "preview": preview}) from exc
