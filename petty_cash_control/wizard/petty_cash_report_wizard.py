from odoo import fields, models


class PettyCashReportWizard(models.TransientModel):
    _name = "petty.cash.report.wizard"
    _description = "Reporte de caja chica"

    date_from = fields.Date(required=True, default=lambda self: fields.Date.start_of(fields.Date.today(), "month"))
    date_to = fields.Date(required=True, default=fields.Date.today)
    box_ids = fields.Many2many("petty.cash.box", string="Cajas")
    category_ids = fields.Many2many("petty.cash.category", string="Categorías")
    state = fields.Selection([("all", "Todos"), ("approved", "Aprobados")], default="approved", required=True)

    def action_print(self):
        self.ensure_one()
        domain = [("date", ">=", self.date_from), ("date", "<=", self.date_to)]
        if self.box_ids:
            domain.append(("box_id", "in", self.box_ids.ids))
        if self.category_ids:
            domain.append(("category_id", "in", self.category_ids.ids))
        if self.state == "approved":
            domain.append(("state", "=", "approved"))
        expenses = self.env["petty.cash.expense"].search(domain, order="date, name")
        return self.env.ref("petty_cash_control.action_report_petty_cash_expenses").report_action(expenses, data={"date_from": str(self.date_from), "date_to": str(self.date_to)})
