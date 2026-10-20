# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import AccessError


class TCGuideCommercialAction(models.Model):
    _inherit = 'tc.guide'

    # Se muestra exclusivamente a usuarios con acceso administrativo.
    # Campo NO almacenado: la actualización no requiere ALTER TABLE.
    commercial_private_line_ids = fields.Many2many(
        'tc.guide.line.private', compute='_compute_private_commercial_lines',
        string='Marcas y proveedores por producto',
        groups='transcash_guias_api.group_tc_sync_admin,base.group_system')

    @api.depends('line_ids')
    def _compute_private_commercial_lines(self):
        Private = self.env['tc.guide.line.private'].sudo()
        for rec in self:
            rec.commercial_private_line_ids = Private.search([('line_id', 'in', rec.line_ids.ids)])

    def action_view_commercial_lines(self):
        self.ensure_one()
        if not (self.env.user.has_group('transcash_guias_api.group_tc_sync_admin') or
                self.env.user.has_group('base.group_system')):
            raise AccessError(_('No tiene autorización para consultar marcas y proveedores de productos.'))
        action = self.env.ref('transcash_guias_api.action_tc_private_lines').read()[0]
        action['domain'] = [('line_id', 'in', self.line_ids.ids)]
        action['context'] = {'search_default_group_by_guide': 0}
        return action


class TCGuidePrivateDetails(models.Model):
    _inherit = 'tc.guide.line.private'

    # Campos no almacenados: no se modifica el esquema físico de res.partner.
    guide_id = fields.Many2one('tc.guide', related='line_id.guide_id', readonly=True)
    sku = fields.Char(related='line_id.sku', readonly=True)
    product_description = fields.Char(related='line_id.name', readonly=True)
