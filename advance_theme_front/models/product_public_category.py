from odoo import _, api, fields, models

class ProductPublicCategory(models.Model):
    _inherit = 'product.public.category'

    is_show = fields.Boolean('Mostrar en carrusel?', default=False)

    