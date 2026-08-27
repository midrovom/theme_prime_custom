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
        string="Fondo aprobado",
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
        "box_id.fund_ids.state",
        "box_id.fund_ids.amount",
        "box_id.expense_ids.state",
        "box_id.expense_ids.amount",
        "box_id.settlement_ids.state",
        "box_id.settlement_ids.return_amount",
        "return_amount",
        "state",
    )
    def _compute_fund_balances(self):
        for rec in self:
            box = rec.box_id
            if not box:
                rec.approved_fund_amount = 0.0
                rec.balance_after_settlement = 0.0
                continue
            approved_funds = sum(
                box.fund_ids.filtered(lambda fund: fund.state == "approved").mapped("amount")
            )
            approved_expenses = sum(
                box.expense_ids.filtered(lambda expense: expense.state == "approved").mapped("amount")
            )
            closed_returns = sum(
                box.settlement_ids.filtered(
                    lambda settlement: settlement.state == "closed"
                ).mapped("return_amount")
            )
            pending_current_return = rec.return_amount if rec.state != "closed" else 0.0
            rec.approved_fund_amount = approved_funds
            rec.balance_after_settlement = (
                approved_funds
                - approved_expenses
                - closed_returns
                - pending_current_return
            )
