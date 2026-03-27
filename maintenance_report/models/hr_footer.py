# from odoo import models, fields, api

# class HrFooter(models.Model):
#     _name = 'hr.footer'
#     _description = 'Footer'

#     descripcion = fields.Text(string="Descripción")

from odoo import models, fields

class ResCompany(models.Model):
    _inherit = 'res.company'

    footer = fields.Html(string="Footer de Factura")

    
