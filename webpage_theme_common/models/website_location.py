import re
from odoo import models, fields, api

class WebsiteLocation(models.Model):
    _name = 'website.location'

    name = fields.Char(string="Nombre del Local", required=True)
    city = fields.Char(string="Ciudad", required=True)
    address = fields.Char(string="Dirección (Google Maps)", help="Dirección completa")

    latitude = fields.Char(string="Latitud")
    longitude = fields.Char(string="Longitud")

    @api.onchange('address')
    def _onchange_address(self):
        if self.address:
            # Buscar patrón @lat,lng en la URL
            match = re.search(r'@(-?\d+\.\d+),(-?\d+\.\d+)', self.address)
            if match:
                self.latitude = match.group(1)
                self.longitude = match.group(2)
