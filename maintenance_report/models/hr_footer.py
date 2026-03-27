# from odoo import models, fields, api

# class HrFooter(models.Model):
#     _name = 'hr.footer'
#     _description = 'Footer'

#     descripcion = fields.Text(string="Descripción")

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

class ResCompany(models.Model):
    _inherit = 'res.company'
    
    footer = fields.Html('Footer de Factura')
    
