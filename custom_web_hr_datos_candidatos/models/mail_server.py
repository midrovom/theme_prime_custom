from odoo import models, fields

class IrMailServer(models.Model):
    _inherit = 'ir.mail_server'

    is_recruitment_server = fields.Boolean(string="Correo de Reclutamiento")
