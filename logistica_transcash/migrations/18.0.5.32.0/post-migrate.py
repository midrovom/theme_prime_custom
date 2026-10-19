"""V5.32: desactivar en BBDD menús por guía heredados de instalaciones previas.

Se desactivan SOLO XMLIDs conocidos del propio módulo. No borrar menús,
acciones, guías ni pagos históricos. No afectar menús de terceros.
"""
import logging
from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)

_LEGACY_MENUS = (
    'menu_transcash_pagos',
    'menu_transcash_activas',
    'menu_transcash_incidentes',
    'menu_transcash_carga',
)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    Menu = env['ir.ui.menu'].sudo().with_context(active_test=False)
    changed = []
    for name in _LEGACY_MENUS:
        menu = env.ref('logistica_transcash.' + name, raise_if_not_found=False)
        if menu and menu.exists():
            Menu.browse(menu.id).write({'active': False, 'name': 'Menú histórico desactivado'})
            changed.append(name)
    # También hay bases antiguas con menús duplicados del módulo y otros XMLIDs.
    # Solo esos menús de ESTE módulo se cierran, nunca registros de terceros.
    ids = env['ir.model.data'].sudo().search([
        ('module', '=', 'logistica_transcash'), ('model', '=', 'ir.ui.menu'),
    ]).mapped('res_id')
    copies = Menu.browse(ids).exists().filtered(
        lambda m: 'liquidacion' in (m.name or '').lower() and
        ('guía' in (m.name or '').lower() or 'guia' in (m.name or '').lower())
    )
    if copies:
        copies.write({'active': False, 'name': 'Menú histórico desactivado'})
    _logger.info('Transcash 5.32: menús obsoletos cerrados: %s; duplicados: %s', changed, len(copies))
