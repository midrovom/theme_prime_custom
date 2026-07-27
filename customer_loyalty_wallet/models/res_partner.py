from odoo import fields, models, _
from odoo.exceptions import UserError


class ResPartner(models.Model):
    _inherit = "res.partner"

    wallet_ids = fields.One2many(
        "loyalty.wallet", "partner_id", string="Billeteras"
    )
    wallet_count = fields.Integer(compute="_compute_wallet_data")
    wallet_balance = fields.Monetary(
        string="Saldo de billetera",
        compute="_compute_wallet_data",
        currency_field="company_currency_id",
    )
    company_currency_id = fields.Many2one(
        "res.currency", compute="_compute_company_currency"
    )

    def _compute_company_currency(self):
        for partner in self:
            partner.company_currency_id = self.env.company.currency_id

    def _compute_wallet_data(self):
        Wallet = self.env["loyalty.wallet"].sudo()
        for partner in self:
            wallets = Wallet.search(
                [
                    ("partner_id", "=", partner.commercial_partner_id.id),
                    ("company_id", "=", self.env.company.id),
                ]
            )
            partner.wallet_count = len(wallets)
            partner.wallet_balance = sum(wallets.mapped("balance"))

    def action_open_wallet(self):
        self.ensure_one()
        wallet = self.env["loyalty.wallet"].search(
            [
                ("partner_id", "=", self.commercial_partner_id.id),
                ("company_id", "=", self.env.company.id),
            ],
            limit=1,
        )
        if not wallet:
            return self.action_create_wallet()
        return {
            "type": "ir.actions.act_window",
            "name": _("Billetera"),
            "res_model": "loyalty.wallet",
            "res_id": wallet.id,
            "view_mode": "form",
            "target": "current",
        }

    def action_create_wallet(self):
        self.ensure_one()
        existing = self.env["loyalty.wallet"].search(
            [
                ("partner_id", "=", self.commercial_partner_id.id),
                ("company_id", "=", self.env.company.id),
            ],
            limit=1,
        )
        if existing:
            raise UserError(_("Este cliente ya tiene una billetera en la compañía actual."))
        wallet = self.env["loyalty.wallet"].create(
            {"partner_id": self.commercial_partner_id.id}
        )
        return {
            "type": "ir.actions.act_window",
            "name": _("Billetera"),
            "res_model": "loyalty.wallet",
            "res_id": wallet.id,
            "view_mode": "form",
            "target": "current",
        }
