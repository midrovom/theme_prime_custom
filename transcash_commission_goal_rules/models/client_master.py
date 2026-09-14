from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from .client_utils import normalize_client_name


class CommissionClient(models.Model):
    _name = "commission.client"
    _description = "Cliente para comisiones"
    _order = "name, id"
    _rec_name = "name"

    name = fields.Char(string="Cliente", required=True, index=True)
    normalized_name = fields.Char(
        string="Nombre normalizado",
        compute="_compute_normalized_name",
        store=True,
        index=True,
        readonly=True,
    )
    active = fields.Boolean(default=True)
    created_from_sales = fields.Boolean(
        string="Creado desde ventas",
        default=False,
        readonly=True,
    )
    notes = fields.Text(string="Notas")

    _sql_constraints = [
        (
            "commission_client_normalized_name_unique",
            "unique(normalized_name)",
            "Ya existe un cliente con ese nombre para efectos de comisiones.",
        ),
    ]

    @api.depends("name")
    def _compute_normalized_name(self):
        for rec in self:
            rec.normalized_name = normalize_client_name(rec.name)

    @api.constrains("name")
    def _check_name(self):
        for rec in self:
            if not normalize_client_name(rec.name):
                raise ValidationError(_("Debe indicar un nombre de cliente válido."))

    @api.model
    def get_or_create_from_sale(self, name):
        clean_name = str(name or "").strip()
        normalized = normalize_client_name(clean_name)
        if not normalized:
            return self.browse()

        client = self.sudo().search([("normalized_name", "=", normalized)], limit=1)
        if client:
            return client

        # The unique SQL key is the final data-integrity guard. Normal Odoo
        # synchronizations execute in one transaction, so a search followed by
        # create avoids adding any Python dependency beyond Odoo itself.
        return self.sudo().create({
            "name": clean_name,
            "created_from_sales": True,
        })


class CommissionSaleClientMaster(models.Model):
    _inherit = "commission.sale"

    client_id = fields.Many2one(
        "commission.client",
        string="Cliente maestro",
        index=True,
        ondelete="restrict",
        help="Cliente normalizado creado automáticamente desde las ventas.",
    )

    @api.model_create_multi
    def create(self, vals_list):
        prepared = []
        Client = self.env["commission.client"]
        for original in vals_list:
            vals = dict(original)
            if vals.get("client_id"):
                client = Client.browse(vals["client_id"]).exists()
                if client:
                    vals.setdefault("client", client.name)
            elif vals.get("client"):
                client = Client.get_or_create_from_sale(vals.get("client"))
                if client:
                    vals["client_id"] = client.id
            prepared.append(vals)
        return super().create(prepared)

    def write(self, vals):
        vals = dict(vals)
        Client = self.env["commission.client"]
        if "client_id" in vals and vals.get("client_id"):
            client = Client.browse(vals["client_id"]).exists()
            if client:
                vals.setdefault("client", client.name)
        elif "client" in vals:
            client = Client.get_or_create_from_sale(vals.get("client"))
            vals["client_id"] = client.id if client else False
        return super().write(vals)
