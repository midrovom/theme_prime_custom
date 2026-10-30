"""One-time compatibility for installations that skipped the earlier data updates."""
import logging

from odoo import api, SUPERUSER_ID
from odoo.addons.transcash_dispatch_analysis.services.maintenance import required_upgrade_steps

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    steps = required_upgrade_steps(version)
    if not steps:
        _logger.info("Despachos: versión instalada %s; no se requiere reconstruir datos históricos", version)
        return
    _logger.info("Despachos: conversión histórica única desde %s; pasos: %s", version, ", ".join(steps))
    env = api.Environment(cr, SUPERUSER_ID, {})
    if "cities" in steps:
        env["dispatch.sla"]._initialize_city_defaults()
    if "unique_records" in steps:
        env["dispatch.invoice"]._initialize_unique_records()
    _logger.info("Despachos: conversión histórica terminada; se conserva en la transacción de actualización")
