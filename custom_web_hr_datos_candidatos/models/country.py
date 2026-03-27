from odoo import _, api, fields, models
import logging

_logger = logging.getLogger(__name__)

class Country(models.Model):
    _inherit = 'res.country'

    emoji_flag = fields.Char(compute='_compute_emoji_flag', store=False)
    
    def _compute_emoji_flag(self):
        for country in self:
            if country.code:
                # Convertir código de país a emoji (ej: US → 🇺🇸)
                country.emoji_flag = self._get_flag_emoji(country.code)
            else:
                country.emoji_flag = ''
    
    def _get_flag_emoji(self, country_code):
        """Convierte código de país (2 letras) a emoji de bandera"""
        if not country_code or len(country_code) != 2:
            return ''
        offset = 127397
        return chr(ord(country_code[0].upper()) + offset) + chr(ord(country_code[1].upper()) + offset)
    