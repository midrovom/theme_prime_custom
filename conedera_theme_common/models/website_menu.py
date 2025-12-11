from odoo import models, fields

class WebsiteMenu(models.Model):
    _inherit = "website.menu"

    icon_image = fields.Binary(string="Icono del menú", attachment=True)
