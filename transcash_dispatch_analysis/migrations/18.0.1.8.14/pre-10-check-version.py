"""Protect databases with a previously committed external-identity merge.
No invoice table scans, writes, or reconstruction during this upgrade.
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    parts = tuple(int(p) for p in version.split('.'))
    release = parts[2:] if parts[:2] == (18, 0) else parts
    if (1, 8, 11) <= release < (1, 8, 13):
        raise ValueError('Despachos: se detectó la versión instalada 1.8.11/12, que podía fusionar facturas diferentes. '
                         'Restaure el respaldo anterior o valide y recupere los datos antes de actualizar.')
    _logger.info('Despachos 1.8.14: numeración visible dinámica; sin conversión histórica de facturas.')
