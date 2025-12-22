from odoo import models, fields

class ProductAttribute(models.Model):
    _inherit = 'product.attribute'

    attribute_custom = fields.Boolean(string="Atributos para productos")
