import json

from odoo import api, fields, models


class ConederaMobileSyncLog(models.Model):
    _name = "conedera.mobile.sync.log"
    _description = "Sincronización App de Campo"
    _order = "create_date desc, id desc"

    client_uuid = fields.Char(required=True, index=True, readonly=True)
    user_id = fields.Many2one("res.users", required=True, default=lambda self: self.env.user, index=True, readonly=True)
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company, index=True, readonly=True)
    operation_type = fields.Selection(
        [
            ("visit", "Visita"),
            ("catastro", "Nuevo catastro"),
            ("catastro_update", "Actualización de catastro"),
        ],
        required=True,
        index=True,
        readonly=True,
    )
    state = fields.Selection(
        [
            ("pending", "Pendiente"),
            ("synced", "Sincronizado"),
            ("warning", "Sincronizado con advertencia"),
            ("error", "Error"),
            ("conflict", "Conflicto"),
        ],
        default="pending",
        required=True,
        index=True,
        readonly=True,
    )
    payload_json = fields.Text(readonly=True)
    result_model = fields.Char(readonly=True)
    result_id = fields.Integer(readonly=True)
    message = fields.Text(readonly=True)
    synced_at = fields.Datetime(readonly=True)

    _sql_constraints = [
        ("client_uuid_unique", "unique(client_uuid)", "Esta operación móvil ya fue recibida."),
    ]

    @api.model
    def _payload_dump(self, payload):
        return json.dumps(payload or {}, ensure_ascii=False, sort_keys=True, default=str)
