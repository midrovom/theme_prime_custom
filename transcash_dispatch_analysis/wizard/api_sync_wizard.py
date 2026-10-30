from odoo import fields, models, _
from odoo.exceptions import UserError
from ..services.api_import import ENDPOINT


class DispatchAPISyncWizard(models.TransientModel):
    _name = "dispatch.api.sync.wizard"
    _description = "Sincronizar despachos desde API Administrator"
    _check_company_auto = True

    company_id = fields.Many2one("res.company", default=lambda self: self.env.company, required=True, readonly=True)
    source_id = fields.Many2one("dispatch.source", string="Fuente de datos", readonly=True, check_company=True,
        default=lambda self: self.env["dispatch.source"].search([("company_id", "=", self.env.company.id)],
            order="api_sync_enabled desc,id", limit=1))
    endpoint = fields.Char(string="API", default=ENDPOINT, readonly=True)
    last_result = fields.Text(related="source_id.api_last_message", readonly=True, string="Último resultado")
    snapshot_state = fields.Selection(related="source_id.api_snapshot_state", readonly=True, string="Estado de importación")

    def action_sync(self):
        self.ensure_one()
        if not self.source_id:
            raise UserError(_("La sincronización no está configurada para esta empresa. Contacta al administrador."))
        return self.source_id.action_sync_api()
