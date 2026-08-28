from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class PettyCashExpense(models.Model):
    _inherit = "petty.cash.expense"

    def _validate_expense_data(self):
        """Mantiene las validaciones funcionales sin exigir archivos adjuntos."""
        for rec in self:
            if not rec.supplier_id:
                raise ValidationError(_("Debe seleccionar el proveedor."))
            if not rec.beneficiary_id:
                raise ValidationError(_("Debe seleccionar el beneficiario."))
            if not rec.department_id:
                raise ValidationError(
                    _("Debe seleccionar el departamento al que corresponde el gasto.")
                )
            if rec.department_id.company_id and rec.department_id.company_id != rec.company_id:
                raise ValidationError(
                    _("El departamento debe pertenecer a la misma compañía de la caja.")
                )

    def action_print_receipt(self):
        self.ensure_one()
        return self.env.ref(
            "petty_cash_receipt_extension.action_report_petty_cash_expense_receipt"
        ).report_action(self)


class PettyCashSettlement(models.Model):
    _inherit = "petty.cash.settlement"

    approved_fund_amount = fields.Monetary(
        string="Fondo máximo",
        compute="_compute_fund_balances",
        currency_field="currency_id",
    )
    balance_after_settlement = fields.Monetary(
        string="Saldo luego de la liquidación",
        compute="_compute_fund_balances",
        currency_field="currency_id",
    )

    @api.depends(
        "box_id",
        "box_id.maximum_amount",
        "expense_ids.amount",
        "expense_ids.state",
    )
    def _compute_fund_balances(self):
        for rec in self:
            box = rec.box_id
            if not box:
                rec.approved_fund_amount = 0.0
                rec.balance_after_settlement = 0.0
                continue
            settlement_expenses = sum(
                rec.expense_ids.filtered(
                    lambda expense: expense.state == "approved"
                ).mapped("amount")
            )
            rec.approved_fund_amount = box.maximum_amount
            rec.balance_after_settlement = box.maximum_amount - settlement_expenses

    def _check_other_pending_settlement(self):
        """Solo admite una liquidación no finalizada por caja."""
        pending_states = ("draft", "submitted", "approved", "rejected")
        for rec in self:
            if not rec.box_id or rec.state not in pending_states:
                continue
            other = self.search(
                [
                    ("box_id", "=", rec.box_id.id),
                    ("state", "in", pending_states),
                    ("id", "!=", rec.id),
                ],
                limit=1,
            )
            if other:
                raise ValidationError(
                    _(
                        "La caja %(box)s ya tiene la liquidación pendiente %(settlement)s. "
                        "Debe cerrarla o anularla antes de crear otra."
                    )
                    % {"box": rec.box_id.display_name, "settlement": other.display_name}
                )

    @api.model_create_multi
    def create(self, vals_list):
        box_ids = sorted({vals.get("box_id") for vals in vals_list if vals.get("box_id")})
        if box_ids:
            # Serializa altas por caja y evita dos liquidaciones simultáneas.
            self.env.cr.execute(
                "SELECT id FROM petty_cash_box WHERE id IN %s FOR UPDATE",
                [tuple(box_ids)],
            )
            existing = self.search(
                [
                    ("box_id", "in", box_ids),
                    ("state", "in", ("draft", "submitted", "approved", "rejected")),
                ],
                limit=1,
            )
            if existing:
                raise ValidationError(
                    _(
                        "La caja %(box)s ya tiene la liquidación pendiente %(settlement)s. "
                        "Debe cerrarla o anularla antes de crear otra."
                    )
                    % {
                        "box": existing.box_id.display_name,
                        "settlement": existing.display_name,
                    }
                )
            if len(box_ids) != len(vals_list):
                raise ValidationError(
                    _("No puede crear más de una liquidación pendiente para la misma caja.")
                )
        records = super().create(vals_list)
        records._check_other_pending_settlement()
        return records

    @api.constrains("box_id", "state")
    def _constraint_single_pending_settlement(self):
        self._check_other_pending_settlement()

    def action_load_expenses(self):
        self._check_other_pending_settlement()
        return super().action_load_expenses()

    def action_submit(self):
        self._check_other_pending_settlement()
        return super().action_submit()

    def action_approve(self):
        self._check_other_pending_settlement()
        return super().action_approve()
