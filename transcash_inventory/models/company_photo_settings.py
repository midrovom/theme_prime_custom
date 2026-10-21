# -*- coding: utf-8 -*-
"""Persistent, company-scoped storefront URL used by the photo sync service."""
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, AccessError
from ..services.photo_matcher import DEFAULT_SITE_ROOT, normalize_site_root


class TranscashCompanyPhotoConfiguration(models.Model):
    _inherit = 'res.company'

    transcash_photo_site_url = fields.Char(
        string='URL base de fotografías', default=DEFAULT_SITE_ROOT,
        help='Tienda Odoo pública que contiene /shop y /web/image. Configurable por empresa.')

    @api.model
    def transcash_photo_root(self):
        return normalize_site_root(self.env.company.transcash_photo_site_url or DEFAULT_SITE_ROOT)

    @api.model
    def action_transcash_photo_settings(self):
        if not self.env.user.has_group('base.group_system'):
            raise AccessError(_('Solo un administrador puede modificar la tienda de fotografías.'))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Configuración de fotografías'),
            'res_model': 'res.company',
            'res_id': self.env.company.id,
            'view_mode': 'form',
            'views': [(self.env.ref('transcash_inventory.view_transcash_photo_company_form').id, 'form')],
            'target': 'current',
        }

    @api.constrains('transcash_photo_site_url')
    def _check_transcash_photo_root(self):
        for company in self:
            if company.transcash_photo_site_url:
                try:
                    normalize_site_root(company.transcash_photo_site_url)
                except ValueError as error:
                    raise ValidationError(str(error)) from error

    def write(self, vals):
        if 'transcash_photo_site_url' not in vals:
            return super().write(vals)
        if not self.env.user.has_group('base.group_system'):
            raise AccessError(_('La URL de fotografías solo puede modificarla el administrador.'))
        try:
            vals = dict(vals, transcash_photo_site_url=normalize_site_root(
                vals['transcash_photo_site_url']))
        except ValueError as error:
            raise ValidationError(str(error)) from error
        changed = self.filtered(lambda c: normalize_site_root(
            c.transcash_photo_site_url or DEFAULT_SITE_ROOT) != vals['transcash_photo_site_url'])
        result = super().write(vals)
        # On a real host change, discard links to the previous business's photo
        # site in THIS company only, and restart catalog discovery. Inventory
        # facts/snapshots and other companies are deliberately untouched.
        for company in changed:
            photos = self.env['transcash.inventory.photo'].with_company(company).search([
                ('company_id', '=', company.id)])
            if photos:
                photos.write({'status': 'queued', 'website_url': False,
                              'image_url': False, 'image_thumbnail': False,
                              'next_retry': False, 'last_error': False,
                              'template_id_remote': 0, 'match_type': 'sku'})
            sync = self.env['transcash.inventory.photo.sync'].with_company(company).search([
                ('company_id', '=', company.id)], limit=1)
            if sync:
                sync.reset_scan()
        return result
