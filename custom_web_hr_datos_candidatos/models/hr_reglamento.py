from odoo import models, fields

class HrFooter(models.Model):
    _name = 'hr.reglamento'
    _description = 'Reglamento'

    reglamento = fields.Html(string="Reglamento Interno")

