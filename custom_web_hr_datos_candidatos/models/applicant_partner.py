from odoo import _, api, fields, models

class RecruitmentPartner(models.Model):
    _inherit = 'res.partner'

    birthday = fields.Date(string="Fecha de nacimiento")

    
    