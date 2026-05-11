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

    search_placeholder_direction = fields.Selection([
        ('none', 'Sin dirección'),
        ('left', 'Desde la izquierda'),
        ('right', 'Desde la derecha'),
        ('up', 'Desde arriba'),
        ('down', 'Desde abajo'),
    ], string="Dirección", default='none')

    search_placeholder_activation = fields.Selection([
        ('always', 'Siempre'),
        ('once', 'Solo la primera vez'),
    ], string="Activación", default='always')

    search_placeholder_duration = fields.Float(
        string="Duración (segundos)", default=2.0
    )


