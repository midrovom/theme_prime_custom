from odoo import models, fields, api

class HrFooter(models.Model):
    _name = 'hr.footer'
    _description = 'Footer'

    descripcion = fields.Text(string="Descripción")
