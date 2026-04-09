from odoo import models, fields

class ResUsers(models.Model):
    _inherit = 'res.users'

    email_verification_code = fields.Char()
    email_verified = fields.Boolean(default=False)
