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

    search_placeholder_effect = fields.Selection([
        ('none', 'Sin efecto'),
        ('up_down', 'Arriba-Abajo'),
        ('down_up', 'Abajo-Arriba'),
        ('fade', 'Desvanecer'),
        ('bounce', 'Rebotar'),
    ], string="Efecto del texto", default='none')

