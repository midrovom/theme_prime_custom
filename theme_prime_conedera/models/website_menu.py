from odoo import _, api, fields, models

class WebsiteMenu(models.Model):
    _inherit = 'website.menu'

    icon = fields.Binary(string="Icono")