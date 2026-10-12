from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools.float_utils import float_compare, float_is_zero


class IncentiveRequest(models.Model):
    _name = "incentive.request"
    _description = "Customer Incentive Request"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "id desc"
    _check_company_auto = True

    name = fields.Char(string="Request Number", required=True, copy=False, readonly=True, default="New", tracking=True)
    company_id = fields.Many2one("res.company", string="Company", required=True, default=lambda self: self.env.company, index=True)
    currency_id = fields.Many2one("res.currency", related="company_id.currency_id", store=True, readonly=True)
    request_type_id = fields.Many2one("incentive.request.type", string="Request Type", required=True, tracking=True, ondelete="restrict")
    requester_id = fields.Many2one("res.users", string="Requested By", required=True, default=lambda self: self.env.user, tracking=True, readonly=True)
    salesperson_id = fields.Many2one("res.users", string="Salesperson", tracking=True, help="Salesperson responsible for this incentive request.")
    customer_id = fields.Many2one("res.partner", string="Beneficiary Customer", required=True, tracking=True, check_company=True)
    supplier_id = fields.Many2one("res.partner", string="Supplier to Recover From", required=True, tracking=True, check_company=True)
    request_date = fields.Date(string="Request Date", required=True, default=fields.Date.context_today, tracking=True)
    payment_term_id = fields.Many2one("account.payment.term", string="Supplier Collection Terms", required=True, help="Manually selected native Odoo payment terms for the collection plan.", check_company=True)
    language_id = fields.Many2one("res.lang", string="Document Language", default=lambda self: self._default_language(), help="Language used when printing this request.")
    line_ids = fields.One2many("incentive.request.line", "request_id", string="Products / Programs", copy=True)
    payment_detail_ids = fields.One2many("incentive.payment.detail", "request_id", string="Seller Payment Details", copy=False)
    description = fields.Text(string="Description")

    total_target_qty = fields.Float(string="Total Target Qty", compute="_compute_totals", store=True, digits="Product Unit of Measure")
    amount_total = fields.Monetary(string="Grand Total", currency_field="currency_id", compute="_compute_totals", store=True)
    accounting_amount_total = fields.Monetary(string="Accounting Amount", currency_field="currency_id", compute="_compute_accounting_amount_total")

    state = fields.Selection([
        ("draft", "Draft"),
        ("submitted", "Submitted"),
        ("approved", "Approved"),
        ("execution", "In Progress"),
        ("beneficiary_paid", "Paid to Beneficiary"),
        ("pending_collection", "Pending Supplier Collection"),
        ("done", "Closed"),
        ("rejected", "Rejected"),
    ], string="Status", default="draft", required=True, tracking=True, index=True, copy=False)

    beneficiary_method = fields.Selection([
        ("transfer", "Bank Transfer"),
        ("offset", "Accounting Offset"),
    ], string="Beneficiary Settlement Method", default="transfer", required=True, tracking=True)
    collection_method = fields.Selection([
        ("transfer", "Bank Transfer"),
        ("offset", "Accounting Offset"),
    ], string="Supplier Collection Method", default="transfer", required=True, tracking=True)

    # These accounting records are optional references to records created manually in Odoo Accounting.
    # The incentive module intentionally does not create or post invoices, payments or journal entries.
    beneficiary_credit_note_id = fields.Many2one(
        "account.move", string="Existing Beneficiary Credit Note", copy=False,
        domain="[('move_type', '=', 'out_refund'), ('partner_id', '=', customer_id), ('company_id', '=', company_id)]",
        check_company=True,
    )
    beneficiary_payment_id = fields.Many2one(
        "account.payment", string="Existing Beneficiary Payment", copy=False,
        domain="[('partner_id', '=', customer_id), ('company_id', '=', company_id)]",
        check_company=True,
    )
    collection_invoice_id = fields.Many2one(
        "account.move", string="Existing Supplier Collection Invoice", copy=False,
        domain="[('move_type', '=', 'out_invoice'), ('partner_id', '=', supplier_id), ('company_id', '=', company_id)]",
        check_company=True,
    )
    collection_document_reference = fields.Char(string="Collection Document / Invoice Reference", tracking=True)
    collection_document_date = fields.Date(string="Collection Document Date")
    collection_invoice_amount = fields.Monetary(string="Amount to Collect (manually entered)", currency_field="currency_id", default=0.0)
    collection_paid_total = fields.Monetary(string="Collection Registered Total", currency_field="currency_id", compute="_compute_collection_residual", store=True)
    collection_residual = fields.Monetary(string="Open Collection Balance", currency_field="currency_id", compute="_compute_collection_residual", store=True)
    evidence_attachment_ids = fields.Many2many(
        "ir.attachment", "incentive_request_attachment_rel", "request_id", "attachment_id",
        string="Supporting Documents / Payment Evidence",
    )

    @api.model
    def _default_language(self):
        user_lang = self.env.user.lang or "en_US"
        return self.env["res.lang"].search([("code", "=", user_lang), ("active", "=", True)], limit=1)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "New") == "New":
                vals["name"] = self.env["ir.sequence"].next_by_code("incentive.request") or "New"
            if not vals.get("salesperson_id"):
                vals["salesperson_id"] = vals.get("requester_id") or self.env.uid
        return super().create(vals_list)

    @api.depends("line_ids.target_qty", "line_ids.total")
    def _compute_totals(self):
        for request in self:
            request.total_target_qty = sum(request.line_ids.mapped("target_qty"))
            request.amount_total = sum(request.line_ids.mapped("total"))

    @api.depends("amount_total", "beneficiary_credit_note_id.amount_total")
    def _compute_accounting_amount_total(self):
        for request in self:
            request.accounting_amount_total = request.beneficiary_credit_note_id.amount_total if request.beneficiary_credit_note_id else request.amount_total

    @api.depends("collection_invoice_amount", "payment_detail_ids.amount", "payment_detail_ids.direction")
    def _compute_collection_residual(self):
        for request in self:
            paid = sum(request.payment_detail_ids.filtered(lambda line: line.direction == "collection").mapped("amount"))
            request.collection_paid_total = paid
            request.collection_residual = max(request.collection_invoice_amount - paid, 0.0)

    @api.constrains("line_ids")
    def _check_has_lines_when_processed(self):
        for request in self:
            if request.state != "draft" and not request.line_ids:
                raise ValidationError(_("Add at least one product/program line before submitting the request."))

    def _check_approver(self):
        if not (self.env.user.has_group("customer_incentive_management.group_incentive_approver") or self.env.user.has_group("customer_incentive_management.group_incentive_manager")):
            raise UserError(_("You do not have permission to approve incentive requests."))

    def _check_accounting_user(self):
        if not (self.env.user.has_group("customer_incentive_management.group_incentive_accounting") or self.env.user.has_group("customer_incentive_management.group_incentive_manager")):
            raise UserError(_("Only accounting users can record beneficiary settlements and supplier collections."))

    def _post_stage_message(self, message):
        for record in self:
            record.message_post(body=message)

    def action_submit(self):
        for record in self:
            if record.state != "draft":
                raise UserError(_("Only draft requests can be submitted."))
            if not record.line_ids:
                raise UserError(_("Add at least one product/program line."))
            if float_is_zero(record.amount_total, precision_rounding=record.currency_id.rounding):
                raise UserError(_("The grand total must be greater than zero."))
            record.state = "submitted"
            record._post_stage_message(_("Request submitted for approval."))
        return True

    def action_approve(self):
        self._check_approver()
        for record in self:
            if record.state != "submitted":
                raise UserError(_("Only submitted requests can be approved."))
            record.state = "approved"
            record._post_stage_message(_("Request approved."))
        return True

    def action_reject(self):
        self._check_approver()
        for record in self:
            if record.state != "submitted":
                raise UserError(_("Only submitted requests can be rejected."))
            record.state = "rejected"
            record._post_stage_message(_("Request rejected."))
        return True

    def action_reset_to_draft(self):
        self._check_approver()
        for record in self:
            if record.state not in ("rejected", "submitted"):
                raise UserError(_("Only rejected or submitted requests can be reset to draft."))
            record.state = "draft"
        return True

    def action_start_execution(self):
        self._check_approver()
        for record in self:
            if record.state != "approved":
                raise UserError(_("Only approved requests can move to In Progress."))
            record.state = "execution"
            record._post_stage_message(_("Execution started."))
        return True

    def _check_evidence(self, detail_lines=None):
        self.ensure_one()
        detail_lines = detail_lines or self.env["incentive.payment.detail"]
        if not self.evidence_attachment_ids and not any(detail_lines.mapped("evidence_attachment_ids")):
            raise UserError(_("Upload supporting documents or payment evidence before confirming the transaction."))

    def action_pay_beneficiary(self):
        """Confirm a manually recorded settlement; no accounting payment is created here."""
        self._check_accounting_user()
        for record in self:
            if record.state != "execution":
                raise UserError(_("The beneficiary settlement can only be confirmed while the request is In Progress."))
            lines = record.payment_detail_ids.filtered(lambda line: line.direction == "beneficiary" and line.method == record.beneficiary_method)
            if not lines:
                raise UserError(_("Enter at least one manual payment/offset detail for the beneficiary."))
            amount = sum(lines.mapped("amount"))
            if float_compare(amount, record.accounting_amount_total, precision_rounding=record.currency_id.rounding) < 0:
                raise UserError(_("The manually recorded beneficiary settlement is less than the request total."))
            record._check_evidence(lines)
            record.state = "beneficiary_paid"
            record._post_stage_message(_("Beneficiary settlement manually recorded. No payment or journal entry was created by this module."))
        return True

    def action_start_collection(self):
        """Record that supplier collection is starting after entering its document manually."""
        self._check_accounting_user()
        for record in self:
            if record.state != "beneficiary_paid":
                raise UserError(_("Record the beneficiary settlement before starting supplier collection."))
            if not record.collection_document_reference:
                raise UserError(_("Enter the supplier collection document or invoice reference manually."))
            if record.collection_invoice_amount <= 0:
                raise UserError(_("Enter a collection amount greater than zero."))
            if record.collection_document_date and record.collection_document_date < record.request_date:
                # Historical documents can exist; this is a warning-level business rule, so do not block them.
                pass
            record.state = "pending_collection"
            record._post_stage_message(_("Supplier collection manually registered with reference %(ref)s and payment terms %(terms)s. No invoice was created by this module.") % {
                "ref": record.collection_document_reference,
                "terms": record.payment_term_id.display_name or _("Not specified"),
            })
        return True

    def _validate_collection_details(self, expected_method):
        self.ensure_one()
        if self.state != "pending_collection":
            raise UserError(_("The request must be Pending Supplier Collection."))
        lines = self.payment_detail_ids.filtered(lambda line: line.direction == "collection" and line.method == expected_method)
        if not lines:
            raise UserError(_("Enter at least one manual collection detail with the selected method."))
        self._check_evidence(lines)
        over = float_compare(self.collection_paid_total, self.collection_invoice_amount, precision_rounding=self.currency_id.rounding)
        if over > 0:
            raise UserError(_("The manually registered collection total cannot exceed the amount to collect."))
        return lines

    def action_collect_by_transfer(self):
        self._check_accounting_user()
        for record in self:
            record._validate_collection_details("transfer")
            if float_is_zero(record.collection_residual, precision_rounding=record.currency_id.rounding):
                record.state = "done"
                record._post_stage_message(_("Supplier collection fully recorded by bank transfer. Actual accounting payment must be registered separately in Odoo Accounting."))
            else:
                record._post_stage_message(_("Supplier transfer manually recorded. Remaining balance: %s. This module did not create an accounting payment.") % record.collection_residual)
        return True

    def action_apply_supplier_offset(self):
        self._check_accounting_user()
        for record in self:
            record._validate_collection_details("offset")
            if float_is_zero(record.collection_residual, precision_rounding=record.currency_id.rounding):
                record.state = "done"
                record._post_stage_message(_("Supplier offset manually recorded in the request. Perform and reconcile the actual offset in Odoo Accounting separately."))
            else:
                record._post_stage_message(_("Supplier offset manually recorded. Remaining balance: %s. Perform the accounting reconciliation separately in Odoo Accounting.") % record.collection_residual)
        return True

    def action_close(self):
        self._check_accounting_user()
        for record in self:
            if record.state != "pending_collection":
                raise UserError(_("Only requests pending supplier collection can be closed."))
            if not float_is_zero(record.collection_residual, precision_rounding=record.currency_id.rounding):
                raise UserError(_("The manually registered collection details must settle the full amount before closing."))
            record.state = "done"
        return True


class IncentiveRequestLine(models.Model):
    _name = "incentive.request.line"
    _description = "Customer Incentive Request Line"
    _order = "sequence, id"

    sequence = fields.Integer(default=10)
    request_id = fields.Many2one("incentive.request", required=True, ondelete="cascade", index=True)
    company_id = fields.Many2one(related="request_id.company_id", store=True, readonly=True)
    currency_id = fields.Many2one(related="request_id.currency_id", store=True, readonly=True)
    product_id = fields.Many2one("product.product", string="Product", required=True, check_company=True, domain="[('sale_ok', '=', True)]")
    product_code = fields.Char(string="Product No.", related="product_id.default_code", readonly=True)
    program_type = fields.Char(string="Program Type", required=True)
    date_from = fields.Date(string="From Date", required=True)
    date_to = fields.Date(string="To Date", required=True)
    unit_price = fields.Monetary(string="Unit", currency_field="currency_id", required=True, default=0.0)
    target_qty = fields.Float(string="Target Qty", required=True, default=1.0, digits="Product Unit of Measure")
    total = fields.Monetary(string="Total", currency_field="currency_id", compute="_compute_total", store=True)

    @api.depends("unit_price", "target_qty")
    def _compute_total(self):
        for line in self:
            line.total = line.unit_price * line.target_qty

    @api.constrains("date_from", "date_to", "unit_price", "target_qty")
    def _check_values(self):
        for line in self:
            if line.date_from and line.date_to and line.date_to < line.date_from:
                raise ValidationError(_("To Date cannot be earlier than From Date."))
            if line.unit_price < 0:
                raise ValidationError(_("Unit cannot be negative."))
            if line.target_qty <= 0:
                raise ValidationError(_("Target Qty must be greater than zero."))


class IncentivePaymentDetail(models.Model):
    _name = "incentive.payment.detail"
    _description = "Incentive Seller Payment Detail"
    _order = "date desc, id desc"

    request_id = fields.Many2one("incentive.request", required=True, ondelete="cascade", index=True)
    salesperson_id = fields.Many2one("res.users", string="Salesperson", required=True, default=lambda self: self.env.user)
    direction = fields.Selection([
        ("beneficiary", "Payment to Beneficiary"),
        ("collection", "Collection from Supplier"),
    ], required=True)
    method = fields.Selection([
        ("transfer", "Transfer"),
        ("offset", "Accounting Offset"),
    ], string="Transaction Type", required=True)
    amount = fields.Monetary(string="Amount", currency_field="currency_id", required=True)
    currency_id = fields.Many2one(related="request_id.currency_id", store=True)
    date = fields.Date(string="Date", required=True, default=fields.Date.context_today)
    reference = fields.Char(string="Reference / Payment No.")
    payment_id = fields.Many2one("account.payment", string="Existing Accounting Payment", check_company=True)
    evidence_attachment_ids = fields.Many2many("ir.attachment", "incentive_detail_attachment_rel", "detail_id", "attachment_id", string="Evidence")

    @api.constrains("amount")
    def _check_amount(self):
        for line in self:
            if line.amount <= 0:
                raise ValidationError(_("Payment/offset detail amount must be greater than zero."))
