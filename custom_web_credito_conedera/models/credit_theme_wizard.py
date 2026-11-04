import re
from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError


class ConederaCreditThemeWizard(models.TransientModel):
    _name = 'conedera.credit.theme.wizard'
    _description = 'Colores de crédito por sitio web / empresa'

    website_id = fields.Many2one('website', string='Sitio web / dominio', required=True,
        default=lambda self: self._default_website())
    color_primary = fields.Char(string='Principal (botones y encabezados)')
    color_hover = fields.Char(string='Color al pasar el cursor')
    color_soft = fields.Char(string='Fondo suave')
    color_border = fields.Char(string='Bordes')
    color_text = fields.Char(string='Títulos')

    _theme_css = {
        'color_primary': ('--credit-red', 'var(--o-color-1, var(--primary, #8F2F2F))'),
        'color_hover': ('--credit-red-dark', 'var(--o-color-2, var(--o-color-1, #702121))'),
        'color_soft': ('--credit-red-soft', 'var(--o-color-3, #F8EDED)'),
        'color_border': ('--credit-border', 'var(--o-color-3, #E7E1DF)'),
        'color_text': ('--credit-heading', 'var(--o-color-5, #702121)'),
    }

    @api.model
    def _default_website(self):
        # No usar un parámetro global: cada sitio web conserva su configuración.
        return self.env['website'].search([('company_id', 'in', self.env.user.company_ids.ids)], limit=1)

    @api.model
    def _key(self, website_id, name):
        return 'custom_web_credito_conedera.website_%s.theme_%s' % (website_id, name)

    @api.model
    def _load_website(self, website):
        params = self.env['ir.config_parameter'].sudo()
        return {name: params.get_param(self._key(website.id, name), '') or False
                for name in self._theme_css}

    @api.model
    def default_get(self, fields_list):
        values = super().default_get(fields_list)
        website_id = values.get('website_id')
        website = self.env['website'].browse(website_id).exists() if website_id else self._default_website()
        if website:
            for key, color in self._load_website(website).items():
                if key in fields_list:
                    values[key] = color
        return values

    @api.onchange('website_id')
    def _onchange_website_id(self):
        if self.website_id:
            for name, color in self._load_website(self.website_id).items():
                self[name] = color

    @api.model
    def credit_css_variables(self, website=None):
        website = website or self.env['website'].get_current_website()
        params = self.env['ir.config_parameter'].sudo()
        css = []
        for name, (variable, inherited) in self._theme_css.items():
            value = params.get_param(self._key(website.id, name), '') if website else ''
            if not value or not re.fullmatch(r'#[0-9A-Fa-f]{6}', value):
                value = inherited
            css.append('%s: %s' % (variable, value))
        return ':root { ' + '; '.join(css) + '; }'

    def action_save(self):
        self.ensure_one()
        if not self.env.user.has_group('custom_web_credito_conedera.group_credit_administrator'):
            raise AccessError(_('Solo el administrador de crédito puede configurar los colores.'))
        if self.website_id.company_id and self.website_id.company_id not in self.env.user.company_ids:
            raise AccessError(_('No tiene acceso a la empresa de este sitio web.'))
        params = self.env['ir.config_parameter'].sudo()
        for name in self._theme_css:
            value = (self[name] or '').strip()
            if value and not re.fullmatch(r'#[0-9A-Fa-f]{6}', value):
                raise ValidationError(_('Color hexadecimal inválido: %s.') % self._fields[name].string)
            key = self._key(self.website_id.id, name)
            if value:
                params.set_param(key, value.upper())
            else:
                params.set_param(key, '')
        return {'type': 'ir.actions.act_window_close'}
