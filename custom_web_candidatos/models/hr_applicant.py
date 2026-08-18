from odoo import models, fields

class HrApplicant(models.model):
    _inherit = 'hr.applicant'

    portal_user_id = fields.Many2one('res.user', string="Usuario del portal", ondelete="set null")