from odoo import models, fields

class HrFooter(models.Model):
    _name = 'hr.footer'
    _description = 'Footer'

    descripcion = fields.Html(string="Descripción")
    # reglamento = fields.Html(string="Reglamento Interno")

