"""Eliminar asociaciones heredadas Administrador -> Usuario tras romper implied_ids.

Antes de v50 Odoo 18 añadía Usuario de crédito automáticamente al asignar
Administrador. La migración quita SOLO Usuario de crédito a administradores;
la cuenta sigue teniendo pleno acceso por el propio rol administrador.
Quienes deseen ambos podrán volver a marcar explícitamente Usuario de crédito.
Los usuarios que únicamente son revisores no se modifican.
"""
import logging
from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    admin = env.ref('custom_web_credito_conedera.group_credit_administrator', raise_if_not_found=False)
    reviewer = env.ref('custom_web_credito_conedera.group_credit_manager', raise_if_not_found=False)
    if not admin or not reviewer:
        return
    # Los grupos ya no están vinculados por herencia en el XML actualizado.
    users = env['res.users'].sudo().with_context(active_test=False).search([
        ('groups_id', 'in', [admin.id]),
        ('groups_id', 'in', [reviewer.id]),
    ])
    for user in users:
        user.write({'groups_id': [(3, reviewer.id)]})
    if users:
        _logger.info('Crédito v50: retirado rol revisor heredado de %d administradores.', len(users))
