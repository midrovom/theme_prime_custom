# -*- coding: utf-8 -*-
"""Reparar solicitudes Portal sin autorización funcional tras actualizar v2.30."""
import logging
from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    summary = env['transcash.acceso.proveedor'].sudo()._tc_reconcile_existing_supplier_accounts()
    _logger.info('v2.31 accesos Portal de proveedores: %s', summary)
