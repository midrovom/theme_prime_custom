from odoo import models, fields
from odoo.exceptions import AccessDenied

class ResUsers(models.Model):
    _inherit = 'res.users'

    email_verification_code = fields.Char()
    email_verified = fields.Boolean(default=False)

    def _check_credentials(self, password, user_agent_env):
        super()._check_credentials(password, user_agent_env)
        if self.has_group('base.group_portal') and not self.email_verified:
            raise AccessDenied(_("Debe verificar su correo antes de iniciar sesión."))