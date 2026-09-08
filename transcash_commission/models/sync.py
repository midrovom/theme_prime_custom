import logging
from datetime import timedelta

import requests

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class CommissionSync(models.Model):
    _name = "commission.sync"
    _description = "Sincronización de ventas para comisiones"
    _order = "create_date desc, id desc"

    name = fields.Char(default=lambda self: _("Sincronización de ventas"), required=True)
    date_from = fields.Date(string="Desde")
    date_to = fields.Date(string="Hasta")
    state = fields.Selection(
        [
            ("draft", "Pendiente"),
            ("running", "Ejecutando"),
            ("done", "Finalizada"),
            ("done_errors", "Finalizada con errores"),
            ("error", "Error"),
        ],
        default="draft",
        required=True,
        index=True,
    )
    started_at = fields.Datetime(string="Inicio", readonly=True)
    finished_at = fields.Datetime(string="Fin", readonly=True)
    rows_received = fields.Integer(string="Filas recibidas", readonly=True)
    created_count = fields.Integer(string="Ventas creadas", readonly=True)
    skipped_count = fields.Integer(string="Duplicadas", readonly=True)
    error_count = fields.Integer(string="Errores", readonly=True)
    log_text = fields.Text(string="Detalle", readonly=True)
    sale_ids = fields.One2many("commission.sale", "sync_id", string="Ventas", readonly=True)

    def _api_config(self):
        icp = self.env["ir.config_parameter"].sudo()
        return {
            "url": icp.get_param("transcash_commission.api_url"),
            "method": icp.get_param("transcash_commission.api_method", "GET").upper(),
            "auth_type": icp.get_param("transcash_commission.api_auth_type", "none"),
            "token": icp.get_param("transcash_commission.api_token"),
            "header_name": icp.get_param("transcash_commission.api_header_name", "X-API-Key"),
            "timeout": int(icp.get_param("transcash_commission.api_timeout", "60") or 60),
            "date_from_param": icp.get_param("transcash_commission.api_date_from_param", "fecha_desde"),
            "date_to_param": icp.get_param("transcash_commission.api_date_to_param", "fecha_hasta"),
        }

    def _fetch_remote_rows(self):
        """INTEGRATION HOOK: obtain rows from the external sales source.

        Replace or override this method when inserting Transcash's definitive
        consumption code. It must return a Python list where each element is a
        dict or positional list accepted by commission.sale._row_as_mapping().

        The generic HTTP implementation below remains operational for testing and
        for simple REST endpoints, but the business insertion logic is isolated
        from transport details.
        """
        self.ensure_one()
        cfg = self._api_config()
        if not cfg["url"]:
            raise UserError(_("Configure la URL del conector o implemente _fetch_remote_rows()."))

        headers = {"Accept": "application/json"}
        if cfg["auth_type"] == "bearer" and cfg["token"]:
            headers["Authorization"] = "Bearer %s" % cfg["token"]
        elif cfg["auth_type"] == "header" and cfg["token"]:
            headers[cfg["header_name"] or "X-API-Key"] = cfg["token"]

        params = {}
        if self.date_from:
            params[cfg["date_from_param"]] = fields.Date.to_string(self.date_from)
        if self.date_to:
            params[cfg["date_to_param"]] = fields.Date.to_string(self.date_to)

        try:
            if cfg["method"] == "POST":
                response = requests.post(cfg["url"], json=params, headers=headers, timeout=cfg["timeout"])
            else:
                response = requests.get(cfg["url"], params=params, headers=headers, timeout=cfg["timeout"])
            response.raise_for_status()
            payload = response.json()
        except requests.RequestException as exc:
            raise UserError(_("Error consultando el origen de ventas: %s") % exc) from exc
        except ValueError as exc:
            raise UserError(_("El origen de ventas no devolvió JSON válido.")) from exc

        if isinstance(payload, dict):
            rows = payload.get("data") or payload.get("result") or payload.get("rows") or []
        else:
            rows = payload
        if not isinstance(rows, list):
            raise UserError(_("La respuesta debe contener una lista de ventas."))
        return rows

    def run_sync(self):
        """Execute one synchronization and always persist its execution result."""
        self.ensure_one()
        self.write({
            "state": "running",
            "started_at": fields.Datetime.now(),
            "finished_at": False,
            "rows_received": 0,
            "created_count": 0,
            "skipped_count": 0,
            "error_count": 0,
            "log_text": False,
        })
        try:
            rows = self._fetch_remote_rows()
            result = self.env["commission.sale"].import_rows(rows, sync=self)
            errors = result["errors"]
            self.write({
                "state": "done_errors" if errors else "done",
                "finished_at": fields.Datetime.now(),
                "rows_received": len(rows),
                "created_count": result["created"],
                "skipped_count": result["skipped"],
                "error_count": len(errors),
                "log_text": "\n".join(errors) if errors else _("Sin errores."),
            })
            return result
        except Exception as exc:
            _logger.exception("Error synchronizing commission sales")
            result = {"created": 0, "skipped": 0, "errors": [str(exc)]}
            self.write({
                "state": "error",
                "finished_at": fields.Datetime.now(),
                "error_count": 1,
                "log_text": str(exc),
            })
            return result

    def action_run(self):
        self.ensure_one()
        result = self.run_sync()
        has_errors = bool(result["errors"])
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Sincronización de ventas"),
                "message": _(
                    "Creadas: %(created)s; duplicadas: %(skipped)s; errores: %(errors)s"
                ) % {
                    "created": result["created"],
                    "skipped": result["skipped"],
                    "errors": len(result["errors"]),
                },
                "type": "warning" if has_errors else "success",
                "sticky": has_errors,
            },
        }

    def action_open_sales(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Ventas sincronizadas"),
            "res_model": "commission.sale",
            "view_mode": "list,form,pivot,graph",
            "domain": [("sync_id", "=", self.id)],
        }

    @api.model
    def cron_synchronize_sales(self):
        icp = self.env["ir.config_parameter"].sudo()
        if icp.get_param("transcash_commission.api_auto_import", "False") != "True":
            return

        today = fields.Date.context_today(self)
        days_back = int(icp.get_param("transcash_commission.api_cron_days_back", "1") or 1)
        sync = self.create({
            "name": _("Sincronización automática %s") % today,
            "date_from": today - timedelta(days=max(days_back - 1, 0)),
            "date_to": today,
        })
        sync.run_sync()
