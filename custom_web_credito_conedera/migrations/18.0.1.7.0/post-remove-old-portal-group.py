"""Eliminar el grupo global obsoleto durante la actualización del módulo.

La autorización vigente se guarda por solicitud (portal_update_scope).
No modificar los permisos de gestión internos ni sus asignaciones.
"""

import logging
from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    xmlid = env['ir.model.data'].sudo().search([
        ('module', '=', 'custom_web_credito_conedera'),
        ('name', '=', 'group_credit_portal_correction'),
    ], limit=1)
    if not xmlid:
        return
    if xmlid.model != 'res.groups':
        _logger.warning('No se elimina el identificador legado: modelo inesperado %s', xmlid.model)
        return
    old_group = env['res.groups'].sudo().browse(xmlid.res_id).exists()
    if old_group:
        old_group.unlink()  # Odoo quita también el grupo de sus usuarios.
        _logger.info('Permiso obsoleto de corrección global eliminado de res.groups.')
    # Evitar conservar un identificador externo apuntando a un registro inexistente.
    if xmlid.exists():
        xmlid.unlink()
