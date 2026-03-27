from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

class ResCompany(models.Model):
    _inherit = 'res.company'
    
    footer = fields.Html('Footer de Factura')
    
