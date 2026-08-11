from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class PettyCashCategory(models.Model):
    _name = "petty.cash.category"
    _description = "Categoría de caja chica"
    _order = "name"

    name = fields.Char(required=True)
    code = fields.Char()
    active = fields.Boolean(default=True)
    expense_limit = fields.Monetary(string="Límite por gasto")
    currency_id = fields.Many2one("res.currency", default=lambda self: self.env.company.currency_id, required=True)
    description = fields.Text()

    _sql_constraints = [("name_company_uniq", "unique(name)", "La categoría ya existe.")]


class PettyCashBox(models.Model):
    _name = "petty.cash.box"
    _description = "Caja chica"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "name"

    name = fields.Char(required=True, tracking=True)
    code = fields.Char(required=True, tracking=True)
    responsible_id = fields.Many2one("res.users", required=True, tracking=True)
    backup_responsible_ids = fields.Many2many("res.users", string="Responsables alternos")
    company_id = fields.Many2one("res.company", default=lambda self: self.env.company, required=True)
    currency_id = fields.Many2one(related="company_id.currency_id", store=True)
    maximum_amount = fields.Monetary(string="Fondo máximo", required=True, tracking=True)
    active = fields.Boolean(default=True)
    notes = fields.Text()
    fund_ids = fields.One2many("petty.cash.fund", "box_id")
    expense_ids = fields.One2many("petty.cash.expense", "box_id")
    settlement_ids = fields.One2many("petty.cash.settlement", "box_id")
    approved_fund = fields.Monetary(compute="_compute_balances", string="Fondos aprobados")
    approved_expense = fields.Monetary(compute="_compute_balances", string="Gastos aprobados")
    returned_amount = fields.Monetary(compute="_compute_balances", string="Devoluciones")
    available_balance = fields.Monetary(compute="_compute_balances", string="Saldo disponible")

    @api.depends("fund_ids.state", "fund_ids.amount", "expense_ids.state", "expense_ids.amount", "settlement_ids.state", "settlement_ids.return_amount")
    def _compute_balances(self):
        for box in self:
            funds = sum(box.fund_ids.filtered(lambda x: x.state == "approved").mapped("amount"))
            expenses = sum(box.expense_ids.filtered(lambda x: x.state == "approved").mapped("amount"))
            returns = sum(box.settlement_ids.filtered(lambda x: x.state == "closed").mapped("return_amount"))
            box.approved_fund = funds
            box.approved_expense = expenses
            box.returned_amount = returns
            box.available_balance = funds - expenses - returns

    @api.constrains("maximum_amount")
    def _check_maximum_amount(self):
        if any(rec.maximum_amount <= 0 for rec in self):
            raise ValidationError(_("El fondo máximo debe ser mayor que cero."))

    _sql_constraints = [("code_company_uniq", "unique(code, company_id)", "El código de caja debe ser único por compañía.")]


class PettyCashFund(models.Model):
    _name = "petty.cash.fund"
    _description = "Entrega o reposición de caja chica"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "date desc, id desc"

    name = fields.Char(default="Nuevo", readonly=True, copy=False)
    date = fields.Date(default=fields.Date.context_today, required=True, tracking=True)
    box_id = fields.Many2one("petty.cash.box", required=True, tracking=True, check_company=True)
    responsible_id = fields.Many2one(related="box_id.responsible_id", store=True)
    fund_type = fields.Selection([("initial", "Entrega inicial"), ("replenishment", "Reposición")], default="replenishment", required=True, tracking=True)
    amount = fields.Monetary(required=True, tracking=True)
    currency_id = fields.Many2one(related="box_id.currency_id", store=True)
    company_id = fields.Many2one(related="box_id.company_id", store=True)
    description = fields.Text(required=True)
    attachment_ids = fields.Many2many("ir.attachment", "petty_cash_fund_attachment_rel", "fund_id", "attachment_id", string="Comprobantes")
    state = fields.Selection([("draft", "Borrador"), ("submitted", "Por aprobar"), ("approved", "Aprobado"), ("rejected", "Rechazado"), ("cancelled", "Anulado")], default="draft", tracking=True)
    approved_by = fields.Many2one("res.users", readonly=True)
    approved_date = fields.Datetime(readonly=True)
    rejection_reason = fields.Text(readonly=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "Nuevo") == "Nuevo":
                vals["name"] = self.env["ir.sequence"].next_by_code("petty.cash.fund") or "Nuevo"
        return super().create(vals_list)

    @api.constrains("amount")
    def _check_amount(self):
        if any(rec.amount <= 0 for rec in self):
            raise ValidationError(_("El valor debe ser mayor que cero."))

    def action_submit(self):
        self.filtered(lambda r: r.state in ("draft", "rejected")).write({"state": "submitted", "rejection_reason": False})

    def action_approve(self):
        if not self.env.user.has_group("petty_cash_control.group_petty_cash_approver"):
            raise UserError(_("No tiene permisos para aprobar fondos."))
        for rec in self:
            if rec.state != "submitted":
                raise UserError(_("Solo se pueden aprobar solicitudes enviadas."))
            if rec.box_id.maximum_amount and rec.box_id.available_balance + rec.amount > rec.box_id.maximum_amount:
                raise ValidationError(_("La aprobación excedería el fondo máximo de la caja."))
            rec.write({"state": "approved", "approved_by": self.env.user.id, "approved_date": fields.Datetime.now()})

    def action_reject(self):
        if not self.env.user.has_group("petty_cash_control.group_petty_cash_approver"):
            raise UserError(_("No tiene permisos para rechazar fondos."))
        self.write({"state": "rejected", "rejection_reason": _("Rechazado por %s") % self.env.user.name})

    def action_cancel(self):
        self.write({"state": "cancelled"})

    def action_reset_draft(self):
        self.write({"state": "draft", "approved_by": False, "approved_date": False})


class PettyCashExpense(models.Model):
    _name = "petty.cash.expense"
    _description = "Gasto de caja chica"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "date desc, id desc"

    name = fields.Char(default="Nuevo", readonly=True, copy=False)
    date = fields.Date(default=fields.Date.context_today, required=True, tracking=True)
    box_id = fields.Many2one("petty.cash.box", required=True, tracking=True, check_company=True)
    responsible_id = fields.Many2one(related="box_id.responsible_id", store=True)
    category_id = fields.Many2one("petty.cash.category", required=True, tracking=True)
    supplier_name = fields.Char(string="Proveedor", required=True)
    supplier_vat = fields.Char(string="RUC/Cédula")
    document_type = fields.Selection([("invoice", "Factura"), ("sale_note", "Nota de venta"), ("receipt", "Recibo"), ("other", "Otro")], default="invoice", required=True)
    document_number = fields.Char(string="N.º de comprobante")
    description = fields.Text(required=True)
    amount = fields.Monetary(required=True, tracking=True)
    currency_id = fields.Many2one(related="box_id.currency_id", store=True)
    company_id = fields.Many2one(related="box_id.company_id", store=True)
    attachment_ids = fields.Many2many("ir.attachment", "petty_cash_expense_attachment_rel", "expense_id", "attachment_id", string="Comprobantes")
    settlement_id = fields.Many2one("petty.cash.settlement", readonly=True, copy=False)
    state = fields.Selection([("draft", "Borrador"), ("submitted", "Por aprobar"), ("approved", "Aprobado"), ("rejected", "Rechazado"), ("cancelled", "Anulado")], default="draft", tracking=True)
    approved_by = fields.Many2one("res.users", readonly=True)
    approved_date = fields.Datetime(readonly=True)
    rejection_reason = fields.Text(readonly=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "Nuevo") == "Nuevo":
                vals["name"] = self.env["ir.sequence"].next_by_code("petty.cash.expense") or "Nuevo"
        return super().create(vals_list)

    @api.constrains("amount", "category_id")
    def _check_amount(self):
        for rec in self:
            if rec.amount <= 0:
                raise ValidationError(_("El valor debe ser mayor que cero."))
            if rec.category_id.expense_limit and rec.amount > rec.category_id.expense_limit:
                raise ValidationError(_("El gasto supera el límite permitido para esta categoría."))

    def action_submit(self):
        for rec in self:
            if not rec.attachment_ids:
                raise ValidationError(_("Debe adjuntar al menos un comprobante."))
            rec.write({"state": "submitted", "rejection_reason": False})

    def action_approve(self):
        if not self.env.user.has_group("petty_cash_control.group_petty_cash_approver"):
            raise UserError(_("No tiene permisos para aprobar gastos."))
        for rec in self:
            if rec.state != "submitted":
                raise UserError(_("Solo se pueden aprobar gastos enviados."))
            if rec.amount > rec.box_id.available_balance:
                raise ValidationError(_("La caja no tiene saldo suficiente para aprobar este gasto."))
            rec.write({"state": "approved", "approved_by": self.env.user.id, "approved_date": fields.Datetime.now()})

    def action_reject(self):
        if not self.env.user.has_group("petty_cash_control.group_petty_cash_approver"):
            raise UserError(_("No tiene permisos para rechazar gastos."))
        self.write({"state": "rejected", "rejection_reason": _("Rechazado por %s") % self.env.user.name})

    def action_cancel(self):
        if any(rec.settlement_id for rec in self):
            raise UserError(_("No puede anular un gasto incluido en una liquidación."))
        self.write({"state": "cancelled"})

    def action_reset_draft(self):
        self.write({"state": "draft", "approved_by": False, "approved_date": False})


class PettyCashSettlement(models.Model):
    _name = "petty.cash.settlement"
    _description = "Liquidación de caja chica"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "date desc, id desc"

    name = fields.Char(default="Nuevo", readonly=True, copy=False)
    date = fields.Date(default=fields.Date.context_today, required=True, tracking=True)
    box_id = fields.Many2one("petty.cash.box", required=True, tracking=True, check_company=True)
    responsible_id = fields.Many2one(related="box_id.responsible_id", store=True)
    expense_ids = fields.One2many("petty.cash.expense", "settlement_id", string="Gastos")
    expense_total = fields.Monetary(compute="_compute_totals", store=True)
    return_amount = fields.Monetary(string="Sobrante devuelto", tracking=True)
    currency_id = fields.Many2one(related="box_id.currency_id", store=True)
    company_id = fields.Many2one(related="box_id.company_id", store=True)
    attachment_ids = fields.Many2many("ir.attachment", "petty_cash_settlement_attachment_rel", "settlement_id", "attachment_id", string="Evidencias")
    notes = fields.Text()
    state = fields.Selection([("draft", "Borrador"), ("submitted", "Por aprobar"), ("approved", "Aprobada"), ("closed", "Cerrada"), ("rejected", "Rechazada"), ("cancelled", "Anulada")], default="draft", tracking=True)
    approved_by = fields.Many2one("res.users", readonly=True)
    approved_date = fields.Datetime(readonly=True)

    @api.depends("expense_ids.amount", "expense_ids.state")
    def _compute_totals(self):
        for rec in self:
            rec.expense_total = sum(rec.expense_ids.filtered(lambda x: x.state == "approved").mapped("amount"))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "Nuevo") == "Nuevo":
                vals["name"] = self.env["ir.sequence"].next_by_code("petty.cash.settlement") or "Nuevo"
        return super().create(vals_list)

    @api.constrains("return_amount")
    def _check_return(self):
        if any(rec.return_amount < 0 for rec in self):
            raise ValidationError(_("El sobrante devuelto no puede ser negativo."))

    def action_load_expenses(self):
        for rec in self:
            if rec.state != "draft":
                continue
            expenses = self.env["petty.cash.expense"].search([("box_id", "=", rec.box_id.id), ("state", "=", "approved"), ("settlement_id", "=", False)])
            expenses.write({"settlement_id": rec.id})

    def action_submit(self):
        for rec in self:
            if not rec.expense_ids and not rec.return_amount:
                raise ValidationError(_("La liquidación debe contener gastos o una devolución."))
            rec.state = "submitted"

    def action_approve(self):
        if not self.env.user.has_group("petty_cash_control.group_petty_cash_approver"):
            raise UserError(_("No tiene permisos para aprobar liquidaciones."))
        self.filtered(lambda x: x.state == "submitted").write({"state": "approved", "approved_by": self.env.user.id, "approved_date": fields.Datetime.now()})

    def action_close(self):
        if not self.env.user.has_group("petty_cash_control.group_petty_cash_approver"):
            raise UserError(_("No tiene permisos para cerrar liquidaciones."))
        for rec in self:
            if rec.state != "approved":
                raise UserError(_("Solo puede cerrar una liquidación aprobada."))
            if rec.return_amount > rec.box_id.available_balance:
                raise ValidationError(_("La devolución supera el saldo disponible de la caja."))
            rec.state = "closed"

    def action_reject(self):
        if not self.env.user.has_group("petty_cash_control.group_petty_cash_approver"):
            raise UserError(_("No tiene permisos para rechazar liquidaciones."))
        self.write({"state": "rejected"})

    def action_cancel(self):
        for rec in self:
            if rec.state == "closed":
                raise UserError(_("Una liquidación cerrada no puede anularse."))
            rec.expense_ids.write({"settlement_id": False})
            rec.state = "cancelled"

    def action_reset_draft(self):
        for rec in self:
            rec.state = "draft"
