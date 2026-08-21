from odoo import api, fields, models
from odoo.exceptions import ValidationError


class PettyCashReportWizard(models.TransientModel):
    _name = "petty.cash.report.wizard"
    _description = "Reporte de caja chica"

    date_from = fields.Date(required=True, default=lambda self: fields.Date.start_of(fields.Date.today(), "month"))
    date_to = fields.Date(required=True, default=fields.Date.today)
    box_ids = fields.Many2many("petty.cash.box", string="Cajas")
    category_ids = fields.Many2many("petty.cash.category", string="Categorías")
    beneficiary_ids = fields.Many2many("res.partner", string="Beneficiarios", domain="[('is_petty_cash_beneficiary', '=', True)]")
    department_ids = fields.Many2many("hr.department", string="Departamentos")
    state = fields.Selection([("all", "Todos"), ("approved", "Aprobados")], default="approved", required=True)

    def action_print(self):
        self.ensure_one()
        if self.date_from > self.date_to:
            raise ValidationError("La fecha inicial no puede ser posterior a la fecha final.")
        domain = [("date", ">=", self.date_from), ("date", "<=", self.date_to)]
        if self.box_ids:
            domain.append(("box_id", "in", self.box_ids.ids))
        if self.category_ids:
            domain.append(("category_id", "in", self.category_ids.ids))
        if self.beneficiary_ids:
            domain.append(("beneficiary_id", "in", self.beneficiary_ids.ids))
        if self.department_ids:
            domain.append(("department_id", "in", self.department_ids.ids))
        if self.state == "approved":
            domain.append(("state", "=", "approved"))
        expenses = self.env["petty.cash.expense"].search(domain, order="date, name")
        data = {
            "expense_ids": expenses.ids,
            "date_from": fields.Date.to_string(self.date_from),
            "date_to": fields.Date.to_string(self.date_to),
        }
        return self.env.ref("petty_cash_control.action_report_petty_cash_expenses").report_action(expenses, data=data)


class PettyCashExpenseReport(models.AbstractModel):
    _name = "report.petty_cash_control.report_expenses_document"
    _description = "Reporte de gastos de caja chica"

    @api.model
    def _get_report_values(self, docids, data=None):
        expense_ids = (data or {}).get("expense_ids") or docids
        docs = self.env["petty.cash.expense"].browse(expense_ids).exists()
        return {
            "doc_ids": docs.ids,
            "doc_model": "petty.cash.expense",
            "docs": docs,
            "data": data or {},
        }
