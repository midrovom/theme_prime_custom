"""Use the same server-side GET/header convention as Inventory Inteligente."""
import json
import logging
from urllib.parse import urlsplit

import requests
from odoo import models, _
from odoo.exceptions import AccessError, UserError
from ..services.api_import import ENDPOINT, MAX_RESPONSE_BYTES

_logger = logging.getLogger(__name__)


class APIAdministrator(models.Model):
    _inherit = "api.administrator"

    def call_dispatch_api(self, timeout=120):
        self.ensure_one()
        if not self.env.su and not self.env.user.has_group("transcash_dispatch_analysis.group_dispatch_operator"):
            raise AccessError(_("Necesita el permiso Operador de despachos."))
        self.check_access_rights("read")
        self.check_access_rule("read")
        if self.company_id != self.env.company or self.name != ENDPOINT or self.type != "get" or self.status != "A":
            raise UserError(_("Seleccione la API GET activa getdatosdespachos de la empresa actual."))
        base, endpoint = (self.url or "").strip(), (self.end_point or "").strip()
        url = "%s/%s" % (base.rstrip("/"), endpoint.lstrip("/")) if endpoint else base
        try:
            parsed = urlsplit(url)
            valid = parsed.scheme in ("http", "https") and parsed.hostname and not parsed.username and not parsed.password
        except ValueError:
            valid = False
        if not valid:
            raise UserError(_("Revise la URL HTTP/HTTPS final en API Administrator."))
        userid, password = (self.user_id or "").strip(), (self.password or "").strip()
        if not userid or not password:
            raise UserError(_("Complete User ID y Password en API Administrator."))
        headers = {"Accept": "application/json", "version": "1", "framework": "PRUEBAS",
                   "userid": userid, "password": password, "deviceid": "000000000000000", "sessionid": "0"}
        response = None
        try:
            response = requests.get(url, headers=headers, timeout=(10, min(120, max(1, int(timeout)))),
                                    allow_redirects=False, stream=True)
            if 300 <= response.status_code < 400:
                raise UserError(_("La API redirecciona. Configure su URL final en API Administrator."))
            response.raise_for_status()
            content, size = [], 0
            for part in response.iter_content(chunk_size=65536):
                size += len(part)
                if size > MAX_RESPONSE_BYTES:
                    raise UserError(_("La respuesta de getdatosdespachos supera 128 MiB."))
                content.append(part)
            result = json.loads(b"".join(content))
        except requests.Timeout:
            raise UserError(_("getdatosdespachos excedió el tiempo de espera. El corte vigente se conserva.")) from None
        except requests.RequestException:
            _logger.warning("Dispatch API request failed for company %s", self.company_id.id)
            raise UserError(_("No se pudo consultar getdatosdespachos. Revise conexión y credenciales en API Administrator.")) from None
        except (ValueError, UnicodeError):
            raise UserError(_("getdatosdespachos no devolvió JSON válido.")) from None
        finally:
            if response is not None:
                response.close()
        if not isinstance(result, (dict, list)):
            raise UserError(_("La respuesta de getdatosdespachos debe ser un objeto o una lista JSON."))
        return result
