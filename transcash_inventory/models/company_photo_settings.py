# -*- coding: utf-8 -*-
"""Company-scoped photo storefront without an added res_company SQL column.

Why non-stored: Odoo can fetch ``res.company`` while installing modules before
it has created columns for newly registered stored company fields. This caused
``psycopg2.errors.UndefinedColumn`` during the upgrade to v1.29.

The same editable field exists in the original settings view but uses a
per-company ir.config_parameter key. This is intentionally not a column on
res_company. Other dashboards, photos and API settings are left untouched.
"""
from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError
from ..services.photo_matcher import DEFAULT_SITE_ROOT, normalize_site_root

PARAM_PREFIX = 'transcash_inventory.photo_site_url.company_'


class TranscashCompanyPhotoConfiguration(models.Model):
    _inherit = 'res.company'

    transcash_photo_site_url = fields.Char(
        string='URL base de fotografías',
        compute='_compute_transcash_photo_site_url',
        inverse='_inverse_transcash_photo_site_url',
        store=False,
        help='Tienda Odoo pública que contiene /shop y /web/image. '
             'Configuración independiente para cada empresa.')

    @api.model
    def _legacy_photo_site_url(self, company_id):
        """Read v1.29 data only IF an earlier successful install made a column.

        Never ask the ORM to fetch a field from a missing column. Existing
        installations that successfully created the old column keep their URL.
        """
        self.env.cr.execute("""            SELECT EXISTS (
                SELECT 1 FROM pg_attribute a
                JOIN pg_class t ON a.attrelid = t.oid
                JOIN pg_namespace n ON t.relnamespace = n.oid
                WHERE t.relname = 'res_company' AND n.nspname = current_schema()
                  AND a.attname = 'transcash_photo_site_url' AND NOT a.attisdropped
            )
        """)
        if not self.env.cr.fetchone()[0]:
            return False
        self.env.cr.execute(
            'SELECT transcash_photo_site_url FROM res_company WHERE id = %s',
            (int(company_id),))
        row = self.env.cr.fetchone()
        return row[0] if row and row[0] else False

    @api.model
    def _photo_site_url_for_company(self, company_id):
        key = '%s%d' % (PARAM_PREFIX, int(company_id))
        saved = self.env['ir.config_parameter'].sudo().get_param(key)
        return normalize_site_root(saved or self._legacy_photo_site_url(company_id)
                                   or DEFAULT_SITE_ROOT)

    @api.depends_context('company')
    def _compute_transcash_photo_site_url(self):
        for company in self:
            company.transcash_photo_site_url = self._photo_site_url_for_company(company.id)

    @api.model
    def transcash_photo_root(self):
        return self._photo_site_url_for_company(self.env.company.id)

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

    def _inverse_transcash_photo_site_url(self):
        if not self.env.user.has_group('base.group_system'):
            raise AccessError(_('La URL de fotografías solo puede modificarla el administrador.'))
        params = self.env['ir.config_parameter'].sudo()
        for company in self:
            try:
                new_root = normalize_site_root(company.transcash_photo_site_url)
                old_root = self._photo_site_url_for_company(company.id)
            except ValueError as error:
                raise ValidationError(str(error)) from error
            params.set_param('%s%d' % (PARAM_PREFIX, company.id), new_root)
            if old_root == new_root:
                continue
            # Invalidate only THIS company's photo links after an actual
            # storefront change. Do not touch its inventory, sales or purchases.
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
