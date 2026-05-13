from odoo import models, fields, _
from odoo.exceptions import AccessDenied

class ResUsers(models.Model):
    _inherit = 'res.users'

    email_verification_code = fields.Char()
    email_verified = fields.Boolean(default=False)
    accept_terms = fields.Boolean(string="Aceptó términos y condiciones", default=False)

    def _check_credentials(self, password, user_agent_env):
        super()._check_credentials(password, user_agent_env)

        # Si es usuario portal y aún no está verificado, bloquear login
        if self.has_group('base.group_portal') and not self.email_verified:
            raise AccessDenied(_("Debe ingresar el código de verificación enviado a su correo para activar la cuenta."))
