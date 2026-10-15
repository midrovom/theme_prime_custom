"""Preserve access of existing assigned portal drivers when upgrading from 4.1.x."""
import logging
from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    group = env.ref('logistica_transcash.group_transcash_chofer', raise_if_not_found=False)
    if not group:
        _logger.warning('Transcash: grupo chofer no encontrado durante migración')
        return
    model = env['transcash.chofer'].sudo()
    guides = env['transcash.guia'].sudo().search([('chofer_usuario_id', '!=', False)])
    already = set()
    for guide in guides:
        user = guide.chofer_usuario_id
        if not user or user.id in already or not user.has_group('base.group_portal'):
            continue
        already.add(user.id)
        if group not in user.groups_id:
            user.write({'groups_id': [(4, group.id)]})
        if not model.search([('usuario_id', '=', user.id)], limit=1):
            model.create({'usuario_id': user.id, 'company_id': guide.company_id.id})
    _logger.info('Transcash: %s cuentas Portal de chofer conservadas en actualización', len(already))
