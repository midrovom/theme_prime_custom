from odoo import models, fields, api

class HrApplicant(models.Model):
    _inherit = 'hr.applicant'

    portal_user_id = fields.Many2one('res.users', string="Usuario del portal", ondelete="set null")