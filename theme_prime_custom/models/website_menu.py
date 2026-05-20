from odoo import _, api, fields, models

class WebsiteMenu(models.Model):
    _inherit = 'website.menu'

    icon = fields.Binary(string="Icono")

class Website(models.Model):
    _inherit = 'website'

    mobile_number = fields.Char(string='Mobile Number')