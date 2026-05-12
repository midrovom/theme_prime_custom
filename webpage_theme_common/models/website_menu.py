from odoo import models, fields

class WebsiteMenu(models.Model):
    _inherit = "website.menu"

    icon_image = fields.Binary(string="Icono del menú", attachment=True)


class Website(models.Model):
    _inherit = "website"

    search_placeholder = fields.Text(
        string="Texto del buscador",
        help="Texto dinámico que se mostrará en el placeholder del buscador."
    )

    search_placeholder_effect = fields.Selection([
        ('none', 'Sin efecto'),
        ('fade', 'Desvanecer'),
        ('bounce', 'Rebotar'),
        ('slide', 'Deslizar'),
        ('flip', 'Volteo'),
        ('shrink', 'Reducir'),
        ('grow', 'Ampliar'),
        ('flash', 'Flash'),
        ('pulse', 'Pulso'),
        ('shake', 'Agitar'),
        ('tada', 'Tada'),
        ('typing', 'Escritura'),
    ], string="Efecto del texto", default='none')

    search_placeholder_duration = fields.Integer(
        string="Duración (segundos)", default=2
    )



