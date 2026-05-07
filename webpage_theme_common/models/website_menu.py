from odoo import models, fields

class WebsiteMenu(models.Model):
    _inherit = "website.menu"

    icon_image = fields.Binary(string="Icono del menú", attachment=True)


class Website(models.Model):
    _inherit = "website"

    search_placeholder = fields.Char(
        string="Texto del buscador",
        help="Texto dinámico que se mostrará en el placeholder del buscador."
    )
