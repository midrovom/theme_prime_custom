from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools.float_utils import float_compare


class LoyaltyWallet(models.Model):
    _name = "loyalty.wallet"
    _description = "Billetera de recompensas"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "id desc"

    name = fields.Char(
        string="Código",
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _("Nuevo"),
        tracking=True,
    )
    partner_id = fields.Many2one(
        "res.partner",
        string="Cliente",
        required=True,
        index=True,
        ondelete="restrict",
        tracking=True,
    )
    company_id = fields.Many2one(
        "res.company",
        string="Compañía",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    currency_id = fields.Many2one(
        "res.currency",
        string="Moneda",
        related="company_id.currency_id",
        store=True,
        readonly=True,
    )
    status = fields.Selection(
        [
            ("active", "Activa"),
            ("blocked", "Bloqueada"),
            ("closed", "Cerrada"),
        ],
        string="Estado",
        default="active",
        required=True,
        tracking=True,
    )
    portal_enabled = fields.Boolean(
        string="Visible en portal",
        default=True,
        tracking=True,
        help="Permite que el cliente consulte esta billetera desde su portal.",
    )
    transaction_ids = fields.One2many(
        "loyalty.wallet.transaction", "wallet_id", string="Movimientos"
    )
    balance = fields.Monetary(
        string="Saldo disponible",
        currency_field="currency_id",
        compute="_compute_totals",
        store=True,
        tracking=True,
    )
    total_credited = fields.Monetary(
        string="Total acumulado",
        currency_field="currency_id",
        compute="_compute_totals",
        store=True,
    )
    total_debited = fields.Monetary(
        string="Total utilizado",
        currency_field="currency_id",
        compute="_compute_totals",
        store=True,
    )
    transaction_count = fields.Integer(
        string="Movimientos", compute="_compute_transaction_count"
    )
    last_movement_date = fields.Datetime(
        string="Último movimiento",
        compute="_compute_totals",
        store=True,
    )
    note = fields.Text(string="Observaciones")

    _sql_constraints = [
        (
            "partner_company_unique",
            "UNIQUE(partner_id, company_id)",
            "El cliente ya tiene una billetera en esta compañía.",
        ),
    ]

    @api.depends(
        "transaction_ids.state",
        "transaction_ids.transaction_type",
        "transaction_ids.amount",
        "transaction_ids.date",
    )
    def _compute_totals(self):
        for wallet in self:
            confirmed = wallet.transaction_ids.filtered(lambda tx: tx.state == "confirmed")
            credits = confirmed.filtered(lambda tx: tx.transaction_type == "credit")
            debits = confirmed.filtered(lambda tx: tx.transaction_type == "debit")
            wallet.total_credited = sum(credits.mapped("amount"))
            wallet.total_debited = sum(debits.mapped("amount"))
            wallet.balance = wallet.total_credited - wallet.total_debited
            wallet.last_movement_date = max(confirmed.mapped("date"), default=False)

    def _compute_transaction_count(self):
        grouped = self.env["loyalty.wallet.transaction"]._read_group(
            [("wallet_id", "in", self.ids)], ["wallet_id"], ["__count"]
        )
        counts = {wallet.id: count for wallet, count in grouped}
        for wallet in self:
            wallet.transaction_count = counts.get(wallet.id, 0)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", _("Nuevo")) == _("Nuevo"):
                vals["name"] = self.env["ir.sequence"].next_by_code(
                    "loyalty.wallet"
                ) or _("Nuevo")
        return super().create(vals_list)

    def _get_sql_balance(self):
        self.ensure_one()
        self.env.cr.execute(
            """
                SELECT COALESCE(SUM(
                    CASE WHEN transaction_type = 'credit' THEN amount ELSE -amount END
                ), 0)
                FROM loyalty_wallet_transaction
                WHERE wallet_id = %s AND state = 'confirmed'
            """,
            [self.id],
        )
        return self.env.cr.fetchone()[0] or 0.0

    def write(self, vals):
        if (
            vals.get("status") == "closed"
            and not self.env.user.has_group(
                "customer_loyalty_wallet.group_wallet_manager"
            )
        ):
            raise UserError(_("Solo un administrador de billetera puede cerrarla."))
        return super().write(vals)

    def action_view_transactions(self):
        self.ensure_one()
        action = self.env.ref(
            "customer_loyalty_wallet.action_loyalty_wallet_transaction"
        ).read()[0]
        action["domain"] = [("wallet_id", "=", self.id)]
        action["context"] = {"default_wallet_id": self.id}
        return action

    def _action_new_transaction(self, transaction_type):
        self.ensure_one()
        if self.status == "closed":
            raise UserError(_("No se pueden registrar movimientos en una billetera cerrada."))
        return {
            "type": "ir.actions.act_window",
            "name": _("Nuevo movimiento"),
            "res_model": "loyalty.wallet.transaction",
            "view_mode": "form",
            "target": "current",
            "context": {
                "default_wallet_id": self.id,
                "default_transaction_type": transaction_type,
            },
        }

    def action_credit(self):
        return self._action_new_transaction("credit")

    def action_debit(self):
        return self._action_new_transaction("debit")

    def action_activate(self):
        self.write({"status": "active"})

    def action_block(self):
        self.write({"status": "blocked"})

    def action_close(self):
        if not self.env.user.has_group("customer_loyalty_wallet.group_wallet_manager"):
            raise UserError(_("Solo un administrador de billetera puede cerrarla."))
        for wallet in self:
            if float_compare(
                wallet.balance,
                0.0,
                precision_rounding=wallet.currency_id.rounding,
            ) != 0:
                raise ValidationError(
                    _("La billetera solo puede cerrarse cuando el saldo sea cero.")
                )
        self.write({"status": "closed", "portal_enabled": False})


class LoyaltyWalletTransaction(models.Model):
    _name = "loyalty.wallet.transaction"
    _description = "Movimiento de billetera"
    _order = "date desc, id desc"

    name = fields.Char(
        string="Número",
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _("Nuevo"),
    )
    wallet_id = fields.Many2one(
        "loyalty.wallet",
        string="Billetera",
        required=True,
        index=True,
        ondelete="restrict",
    )
    partner_id = fields.Many2one(
        "res.partner",
        string="Cliente",
        related="wallet_id.partner_id",
        store=True,
        index=True,
    )
    company_id = fields.Many2one(
        "res.company",
        string="Compañía",
        related="wallet_id.company_id",
        store=True,
        index=True,
    )
    currency_id = fields.Many2one(
        "res.currency",
        string="Moneda",
        related="wallet_id.currency_id",
        store=True,
        readonly=True,
    )
    date = fields.Datetime(
        string="Fecha", required=True, default=fields.Datetime.now, index=True
    )
    transaction_type = fields.Selection(
        [("credit", "Abono"), ("debit", "Consumo")],
        string="Tipo",
        required=True,
        default="credit",
        index=True,
    )
    reason = fields.Selection(
        [
            ("punctual_payment", "Pago puntual"),
            ("campaign_bonus", "Bono de campaña"),
            ("manual_bonus", "Bono manual"),
            ("redemption", "Uso de saldo"),
            ("correction", "Corrección"),
            ("reversal", "Reverso"),
            ("other", "Otro"),
        ],
        string="Motivo",
        required=True,
        default="punctual_payment",
        index=True,
    )
    amount = fields.Monetary(
        string="Valor",
        required=True,
        currency_field="currency_id",
    )
    signed_amount = fields.Monetary(
        string="Valor con signo",
        currency_field="currency_id",
        compute="_compute_signed_amount",
        store=True,
    )
    description = fields.Char(string="Descripción", required=True)
    reference = fields.Char(
        string="Referencia externa",
        help="Ejemplo: cuota, comprobante, ticket o número de autorización.",
    )
    state = fields.Selection(
        [
            ("draft", "Borrador"),
            ("confirmed", "Confirmado"),
            ("cancelled", "Cancelado"),
        ],
        string="Estado",
        default="draft",
        required=True,
        index=True,
    )
    confirmed_by_id = fields.Many2one(
        "res.users", string="Confirmado por", readonly=True
    )
    confirmed_at = fields.Datetime(string="Confirmado el", readonly=True)
    reversal_of_id = fields.Many2one(
        "loyalty.wallet.transaction",
        string="Reversa de",
        readonly=True,
        copy=False,
        ondelete="restrict",
    )
    reversal_id = fields.Many2one(
        "loyalty.wallet.transaction",
        string="Movimiento de reverso",
        compute="_compute_reversal_id",
    )

    _sql_constraints = [
        (
            "amount_positive",
            "CHECK(amount > 0)",
            "El valor del movimiento debe ser mayor que cero.",
        ),
        (
            "one_reversal",
            "UNIQUE(reversal_of_id)",
            "Este movimiento ya fue reversado.",
        ),
    ]

    @api.depends("amount", "transaction_type")
    def _compute_signed_amount(self):
        for tx in self:
            tx.signed_amount = tx.amount if tx.transaction_type == "credit" else -tx.amount

    def _compute_reversal_id(self):
        reversals = self.search([("reversal_of_id", "in", self.ids)])
        by_original = {tx.reversal_of_id.id: tx for tx in reversals}
        for tx in self:
            tx.reversal_id = by_original.get(tx.id)

    @api.constrains("amount")
    def _check_amount(self):
        for tx in self:
            if tx.amount <= 0:
                raise ValidationError(_("El valor debe ser mayor que cero."))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("state", "draft") != "draft":
                raise UserError(
                    _("Los movimientos deben crearse en borrador y confirmarse mediante la acción correspondiente.")
                )
            if vals.get("name", _("Nuevo")) == _("Nuevo"):
                vals["name"] = self.env["ir.sequence"].next_by_code(
                    "loyalty.wallet.transaction"
                ) or _("Nuevo")
        return super().create(vals_list)

    def write(self, vals):
        if "state" in vals and not self.env.context.get("allow_wallet_state_change"):
            raise UserError(
                _("El estado del movimiento solo puede cambiar mediante los botones de acción.")
            )
        protected = {
            "wallet_id",
            "transaction_type",
            "amount",
            "date",
            "reason",
            "description",
            "reference",
        }
        if protected.intersection(vals):
            confirmed = self.filtered(lambda tx: tx.state == "confirmed")
            if confirmed:
                raise UserError(
                    _("Un movimiento confirmado no puede editarse. Use la opción Reversar.")
                )
        return super().write(vals)

    def unlink(self):
        if self.filtered(lambda tx: tx.state == "confirmed"):
            raise UserError(
                _("Los movimientos confirmados no pueden eliminarse. Deben reversarse.")
            )
        return super().unlink()

    def action_confirm(self):
        for tx in self:
            if tx.state != "draft":
                continue
            if tx.wallet_id.status != "active":
                raise ValidationError(
                    _("La billetera debe estar activa para confirmar movimientos.")
                )
            self.env.cr.execute(
                "SELECT id FROM loyalty_wallet WHERE id = %s FOR UPDATE",
                [tx.wallet_id.id],
            )
            if tx.transaction_type == "debit":
                available = tx.wallet_id._get_sql_balance()
                if float_compare(
                    tx.amount,
                    available,
                    precision_rounding=tx.currency_id.rounding,
                ) > 0:
                    raise ValidationError(
                        _(
                            "Saldo insuficiente. Disponible: %(balance)s %(currency)s.",
                            balance=available,
                            currency=tx.currency_id.name,
                        )
                    )
            tx.with_context(allow_wallet_state_change=True).write(
                {
                    "state": "confirmed",
                    "confirmed_by_id": self.env.user.id,
                    "confirmed_at": fields.Datetime.now(),
                }
            )
            tx.wallet_id.message_post(
                body=_(
                    "Movimiento %(movement)s confirmado por %(amount)s %(currency)s. Motivo: %(reason)s.",
                    movement=tx.name,
                    amount=tx.amount,
                    currency=tx.currency_id.name,
                    reason=dict(tx._fields["reason"].selection).get(tx.reason),
                )
            )
        return True

    def action_cancel(self):
        for tx in self:
            if tx.state == "confirmed":
                raise UserError(
                    _("Un movimiento confirmado no puede cancelarse. Use Reversar.")
                )
        self.with_context(allow_wallet_state_change=True).write({"state": "cancelled"})
        return True

    def action_reset_to_draft(self):
        self.filtered(lambda tx: tx.state == "cancelled").with_context(
            allow_wallet_state_change=True
        ).write({"state": "draft"})
        return True

    def action_reverse(self):
        self.ensure_one()
        if not self.env.user.has_group("customer_loyalty_wallet.group_wallet_manager"):
            raise UserError(_("Solo un administrador de billetera puede reversar movimientos."))
        if self.state != "confirmed":
            raise UserError(_("Solo puede reversar un movimiento confirmado."))
        if self.reversal_id:
            raise UserError(_("Este movimiento ya tiene un reverso."))
        reverse_type = "debit" if self.transaction_type == "credit" else "credit"
        reversal = self.create(
            {
                "wallet_id": self.wallet_id.id,
                "transaction_type": reverse_type,
                "reason": "reversal",
                "amount": self.amount,
                "description": _("Reverso de %(name)s: %(description)s", name=self.name, description=self.description),
                "reference": self.reference,
                "reversal_of_id": self.id,
            }
        )
        reversal.action_confirm()
        return {
            "type": "ir.actions.act_window",
            "name": _("Movimiento de reverso"),
            "res_model": "loyalty.wallet.transaction",
            "res_id": reversal.id,
            "view_mode": "form",
            "target": "current",
        }
