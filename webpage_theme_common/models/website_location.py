from odoo import models, fields

class WebsiteLocation(models.Model):
    _name = 'website.location'

    name = fields.Char(string="Nombre del Local", required=True)
    city = fields.Char(string="Ciudad", required=True)
    address = fields.Char(string="Dirección (Google Maps)", help="Dirección completa")

    # Coordenadas
    latitude = fields.Float(string="Latitud", digits=(10, 6), help="Ejemplo: -2.170998")
    longitude = fields.Float(string="Longitud", digits=(10, 6), help="Ejemplo: -79.922359")