from odoo import models, fields

class ProductAttribute(models.Model):
    _inherit = 'product.attribute'

    attribute_custom = fields.Boolean(string="Atributos para productos")
    filter_attribute = fields.Boolean(string="Atributos para filtro")
