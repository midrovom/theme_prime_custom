from odoo import models, fields

class ResCompany(models.Model):
    _inherit = "res.company"

    footer = fields.Text(string="Footer de Reporte")



# class HrFooter(models.Model):
#     _name = 'hr.footer'
#     _description = 'Footer'

#     descripcion = fields.Text(string="Descripción")
