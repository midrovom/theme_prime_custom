from odoo import models, fields

class WebsiteLocation(models.Model):
    _name = 'website.location'

    name = fields.Char(string="Nombre del Local", required=True)
    city = fields.Char(string="Ciudad", required=True)

    # Coordenadas
    latitude = fields.Char(string="Latitud")
    longitude = fields.Char(string="Longitud")
