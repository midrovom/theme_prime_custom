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
    salesperson_id = fields.Many2one("res.users", string="Responsible Salesperson", tracking=True, help="Salesperson associated with the request. This can be different from the user who creates it.")
    customer_id = fields.Many2one("res.partner", string="Beneficiary Customer", required=True, tracking=True, check_company=True)
    supplier_id = fields.Many2one("res.partner", string="Supplier to Recover From", required=True, tracking=True, check_company=True)
    request_date = fields.Date(string="Request Date", required=True, default=fields.Date.context_today, tracking=True)
    payment_term_id = fields.Many2one("account.payment.term", string="Supplier Collection Terms", required=True, help="Select the agreed collection terms when the request is prepared. The invoice is still entered manually in Accounting.")
    language_id = fields.Many2one("res.lang", string="Document Language", default=lambda self: self._default_language(), help="Language used when printing this request.")
    line_ids = fields.One2many("incentive.request.line", "request_id", string="Products / Programs", copy=True)
    payment_detail_ids = fields.One2many("incentive.payment.detail", "request_id", string="Seller Payment Details", copy=False)
    description = fields.Text(string="Description")

    total_target_qty = fields.Float(string="Total Target Qty", compute="_compute_totals", store=True, digits=(16, 2))
    amount_total = fields.Monetary(string="Grand Total", currency_field="currency_id", compute="_compute_totals", store=True)
    accounting_amount_total = fields.Monetary(string="Accounting Amount", currency_field="currency_id", compute="_compute_accounting_amount_total", store=True)

    state = fields.Selection([
        ("draft", "Draft"),
        ("submitted", "Submitted for Approval"),
        ("approved", "Approved"),
        ("execution", "In Execution"),
        ("beneficiary_paid", "Paid to Beneficiary"),
        ("pending_collection", "Pending Supplier Collection"),
        ("done", "Closed"),
        ("rejected", "Rejected"),
    ], string="Status", default="draft", required=True, tracking=True, index=True, copy=False)

    beneficiary_credit_note_id = fields.Many2one(
        "account.move", string="Existing Beneficiary Credit Note", copy=False,
        domain="[('move_type', '=', 'out_refund'), ('partner_id', '=', customer_id), ('company_id', '=', company_id), ('state', '=', 'posted')]",
        check_company=True,
    )
    beneficiary_payment_id = fields.Many2one(
        "account.payment", string="Existing Beneficiary Payment", copy=False,
        domain="[('partner_id', '=', customer_id), ('company_id', '=', company_id)]",
        check_company=True,
    )
    collection_invoice_id = fields.Many2one(
        "account.move", string="Existing Supplier Collection Invoice", copy=False,
        domain="[('move_type', '=', 'out_invoice'), ('partner_id', '=', supplier_id), ('company_id', '=', company_id), ('state', '=', 'posted')]",
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

    can_edit_request = fields.Boolean(compute="_compute_current_user_permissions")
    can_edit_payment_details = fields.Boolean(compute="_compute_current_user_permissions")
    can_edit_evidence = fields.Boolean(compute="_compute_current_user_permissions")
    can_edit_beneficiary_fields = fields.Boolean(compute="_compute_current_user_permissions")
    can_edit_collection_fields = fields.Boolean(compute="_compute_current_user_permissions")

    @api.model
    def _default_language(self):
        user_lang = self.env.user.lang or "en_US"
        return self.env["res.lang"].search([("code", "=", user_lang), ("active", "=", True)], limit=1)

    @api.depends_context("uid")
    @api.depends("requester_id", "state")
    def _compute_current_user_permissions(self):
        user = self.env.user
        is_manager = user.has_group("customer_incentive_management.group_incentive_manager")
        is_treasury = user.has_group("customer_incentive_management.group_incentive_treasury") or user.has_group("customer_incentive_management.group_incentive_accounting") or is_manager
        is_collection = user.has_group("customer_incentive_management.group_incentive_collection") or user.has_group("customer_incentive_management.group_incentive_accounting") or is_manager
        for record in self:
            is_requester = record.requester_id.id == user.id
            record.can_edit_request = is_manager or (is_requester and record.state in ("draft", "rejected"))
            record.can_edit_payment_details = is_manager or (is_treasury and record.state == "execution") or (is_collection and record.state == "pending_collection")
            record.can_edit_evidence = is_manager or (is_requester and record.state in ("draft", "rejected")) or (is_treasury and record.state in ("approved", "execution")) or (is_collection and record.state in ("beneficiary_paid", "pending_collection"))
            record.can_edit_beneficiary_fields = is_manager or (is_treasury and record.state in ("approved", "execution"))
            record.can_edit_collection_fields = is_manager or (is_collection and record.state in ("beneficiary_paid", "pending_collection"))

    @api.model_create_multi
    def create(self, vals_list):
        user = self.env.user
        if not (user.has_group("customer_incentive_management.group_incentive_user") or user.has_group("customer_incentive_management.group_incentive_manager")):
            raise UserError(_("Only requesters or incentive managers can create a request."))
        for vals in vals_list:
            if vals.get("name", "New") == "New":
                vals["name"] = self.env["ir.sequence"].next_by_code("incentive.request") or "New"
            # The logged-in user is always the requester. Salesperson is a separate assignment.
            vals["requester_id"] = user.id
            vals.pop("state", None)
        return super().create(vals_list)

    def write(self, vals):
        if "state" in vals:
            raise UserError(_("Use the workflow buttons to change the request status."))

        user = self.env.user
        is_manager = user.has_group("customer_incentive_management.group_incentive_manager")
        if is_manager:
            return super().write(vals)

        requester_fields = {
            "company_id", "request_type_id", "salesperson_id", "customer_id", "supplier_id", "request_date",
            "payment_term_id", "language_id", "line_ids", "description", "evidence_attachment_ids",
        }
        beneficiary_fields = {"beneficiary_credit_note_id", "beneficiary_payment_id", "evidence_attachment_ids"}
        collection_fields = {
            "collection_document_reference", "collection_document_date", "collection_invoice_amount",
            "collection_invoice_id", "evidence_attachment_ids",
        }
        if not vals:
            return True

        for record in self:
            if (
                user.has_group("customer_incentive_management.group_incentive_user")
                and record.requester_id.id == user.id
                and record.state in ("draft", "rejected")
                and not (set(vals) - requester_fields)
            ):
                continue
            is_treasury = user.has_group("customer_incentive_management.group_incentive_treasury") or user.has_group("customer_incentive_management.group_incentive_accounting")
            is_collection = user.has_group("customer_incentive_management.group_incentive_collection") or user.has_group("customer_incentive_management.group_incentive_accounting")
            if is_treasury and record.state in ("approved", "execution") and not (set(vals) - beneficiary_fields):
                continue
            if is_collection and record.state in ("beneficiary_paid", "pending_collection") and not (set(vals) - collection_fields):
                continue
            raise UserError(_("You do not have permission to edit this request."))
        return super().write(vals)

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

    def _check_group(self, group_xmlid, message):
        if not (self.env.user.has_group(group_xmlid) or self.env.user.has_group("customer_incentive_management.group_incentive_manager")):
            raise UserError(message)

    def _check_approver(self):
        self._check_group("customer_incentive_management.group_incentive_approver", _("You do not have permission to approve incentive requests."))

    def _check_treasury(self):
        user = self.env.user
        if not (user.has_group("customer_incentive_management.group_incentive_treasury") or user.has_group("customer_incentive_management.group_incentive_accounting") or user.has_group("customer_incentive_management.group_incentive_manager")):
            raise UserError(_("Only Treasury can register payment to the beneficiary."))

    def _check_collection(self):
        user = self.env.user
        if not (user.has_group("customer_incentive_management.group_incentive_collection") or user.has_group("customer_incentive_management.group_incentive_accounting") or user.has_group("customer_incentive_management.group_incentive_manager")):
            raise UserError(_("Only Supplier Collection / Accounts Receivable can register supplier collections."))

    def _set_workflow_state(self, new_state):
        # Private method: regular RPC writes to state are blocked in write().
        return super(IncentiveRequest, self).write({"state": new_state})

    def _post_stage_message(self, message):
        for record in self:
            record.message_post(body=message)

    def _check_not_own_approval(self):
        user = self.env.user
        for record in self:
            if record.requester_id.id == user.id or record.salesperson_id.id == user.id:
                raise UserError(_("Separation of duties: you cannot approve or reject a request that you submitted or are assigned to as salesperson."))

    def action_submit(self):
        for record in self:
            if record.state not in ("draft", "rejected"):
                raise UserError(_("Only Draft or Rejected requests can be submitted."))
            if record.requester_id.id != self.env.uid and not self.env.user.has_group("customer_incentive_management.group_incentive_manager"):
                raise UserError(_("Only the requester can submit this request."))
            if not record.line_ids:
                raise UserError(_("Add at least one manual product/program line."))
            if not record.salesperson_id:
                raise UserError(_("Select the salesperson responsible for this request. The requester and salesperson may be different people."))
            if not record.payment_term_id:
                raise UserError(_("Select the supplier collection payment terms before submitting."))
            if float_is_zero(record.amount_total, precision_rounding=record.currency_id.rounding):
                raise UserError(_("The grand total must be greater than zero."))
            if record.amount_total < 0:
                raise UserError(_("The grand total cannot be negative."))
            record._set_workflow_state("submitted")
            record._post_stage_message(_("Request submitted for approval by %s.") % self.env.user.display_name)
        return True

    def action_approve(self):
        self._check_approver()
        self._check_not_own_approval()
        for record in self:
            if record.state != "submitted":
                raise UserError(_("Only requests waiting for approval can be approved."))
            record._set_workflow_state("approved")
            record._post_stage_message(_("Request approved. Treasury is responsible for execution."))
        return True

    def action_reject(self):
        self._check_approver()
        self._check_not_own_approval()
        for record in self:
            if record.state != "submitted":
                raise UserError(_("Only requests waiting for approval can be rejected."))
            record._set_workflow_state("rejected")
            record._post_stage_message(_("Request rejected. The requester can correct it and submit it again."))
        return True

    def action_reset_to_draft(self):
        self._check_approver()
        self._check_not_own_approval()
        for record in self:
            if record.state not in ("submitted", "rejected"):
                raise UserError(_("Only submitted or rejected requests can be reset to Draft."))
            record._set_workflow_state("draft")
            record._post_stage_message(_("Request returned to Draft."))
        return True

    def action_start_execution(self):
        self._check_treasury()
        for record in self:
            if record.state != "approved":
                raise UserError(_("Only approved requests can move to In Execution."))
            record._set_workflow_state("execution")
            record._post_stage_message(_("Execution started by Treasury. Beneficiary settlement details can now be recorded."))
        return True

    def _check_evidence(self, detail_lines=None):
        self.ensure_one()
        detail_lines = detail_lines or self.env["incentive.payment.detail"]
        if not self.evidence_attachment_ids and not any(detail_lines.mapped("evidence_attachment_ids")):
            raise UserError(_("Upload supporting documents or payment evidence before confirming the transaction."))

    def action_pay_beneficiary(self):
        self._check_treasury()
        for record in self:
            if record.state != "execution":
                raise UserError(_("Beneficiary payment can only be confirmed while the request is In Execution."))
            lines = record.payment_detail_ids.filtered(lambda line: line.direction == "beneficiary")
            if not lines:
                raise UserError(_("Enter at least one beneficiary payment or offset detail."))
            amount = sum(lines.mapped("amount"))
            amount_comparison = float_compare(amount, record.accounting_amount_total, precision_rounding=record.currency_id.rounding)
            if amount_comparison < 0:
                raise UserError(_("Beneficiary payment/offset details do not cover the accounting amount."))
            if amount_comparison > 0:
                raise UserError(_("Beneficiary payment/offset details exceed the accounting amount."))
            if any(not line.reference for line in lines):
                raise UserError(_("Enter a reference for every beneficiary transfer or accounting offset."))
            record._check_evidence(lines)
            record._set_workflow_state("beneficiary_paid")
            record._post_stage_message(_("Beneficiary settlement recorded manually. This module did not create a payment or accounting entry."))
        return True

    def action_start_collection(self):
        self._check_collection()
        for record in self:
            if record.state != "beneficiary_paid":
                raise UserError(_("Record beneficiary settlement before starting supplier collection."))
            if not record.collection_document_reference:
                raise UserError(_("Enter the supplier collection document or invoice reference manually."))
            if record.collection_invoice_amount <= 0:
                raise UserError(_("Enter a collection amount greater than zero."))
            if not record.payment_term_id:
                raise UserError(_("The request must have supplier collection terms selected from the beginning."))
            record._set_workflow_state("pending_collection")
            record._post_stage_message(_("Supplier collection started. Document %(ref)s; agreed terms: %(terms)s. The invoice must be created manually in Accounting.") % {
                "ref": record.collection_document_reference,
                "terms": record.payment_term_id.display_name,
            })
        return True

    def action_confirm_supplier_collection(self):
        self._check_collection()
        for record in self:
            if record.state != "pending_collection":
                raise UserError(_("The request must be Pending Supplier Collection."))
            lines = record.payment_detail_ids.filtered(lambda line: line.direction == "collection")
            if not lines:
                raise UserError(_("Enter at least one transfer or accounting offset detail for supplier collection."))
            if any(not line.reference for line in lines):
                raise UserError(_("Enter a reference for every supplier transfer or accounting offset."))
            if float_compare(record.collection_paid_total, record.collection_invoice_amount, precision_rounding=record.currency_id.rounding) > 0:
                raise UserError(_("The registered supplier collection total cannot exceed the amount to collect."))
            record._check_evidence(lines)
            if float_is_zero(record.collection_residual, precision_rounding=record.currency_id.rounding):
                record._set_workflow_state("done")
                record._post_stage_message(_("Supplier collection is fully registered. Actual transfers and offsets must be processed/conciled separately in Odoo Accounting."))
            else:
                record._post_stage_message(_("Supplier collection movement registered. Remaining balance: %s. The request stays Pending Supplier Collection.") % record.collection_residual)
        return True


class IncentiveRequestLine(models.Model):
    _name = "incentive.request.line"
    _description = "Customer Incentive Request Line"
    _order = "sequence, id"

    sequence = fields.Integer(default=10)
    request_id = fields.Many2one("incentive.request", required=True, ondelete="cascade", index=True)
    company_id = fields.Many2one(related="request_id.company_id", store=True, readonly=True)
    currency_id = fields.Many2one(related="request_id.currency_id", store=True, readonly=True)
    product_number = fields.Char(string="Product No.", required=True, help="Enter the product number manually; this is not linked to Odoo's product catalog.")
    program_type = fields.Char(string="Program Type", required=True, help="Enter the program or activity manually, for example Rebate, store repair or advertising.")
    date_from = fields.Date(string="From Date", required=True)
    date_to = fields.Date(string="To Date", required=True)
    unit_price = fields.Monetary(string="Unit", currency_field="currency_id", required=True, default=0.0)
    target_qty = fields.Float(string="Target Qty", required=True, default=1.0, digits=(16, 2))
    total = fields.Monetary(string="Total", currency_field="currency_id", compute="_compute_total", store=True)

    def _check_can_edit_line(self):
        user = self.env.user
        if user.has_group("customer_incentive_management.group_incentive_manager"):
            return
        for line in self:
            request = line.request_id
            if not (request.requester_id.id == user.id and request.state in ("draft", "rejected")):
                raise UserError(_("Only the requester can edit product/program lines while the request is Draft or Rejected."))

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.user.has_group("customer_incentive_management.group_incentive_manager"):
            for vals in vals_list:
                request = self.env["incentive.request"].browse(vals.get("request_id") or self.env.context.get("default_request_id")).exists()
                if not request or request.requester_id.id != self.env.uid or request.state not in ("draft", "rejected"):
                    raise UserError(_("Only the requester can add product/program lines while the request is Draft or Rejected."))
        return super().create(vals_list)

    def write(self, vals):
        if "request_id" in vals and any(line.request_id.id != vals["request_id"] for line in self):
            raise UserError(_("A product/program line cannot be moved to another request."))
        self._check_can_edit_line()
        return super().write(vals)

    def unlink(self):
        self._check_can_edit_line()
        return super().unlink()

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
    salesperson_id = fields.Many2one("res.users", string="Salesperson", required=True, help="Seller associated with this specific payment or offset.")
    direction = fields.Selection([
        ("beneficiary", "Payment to Beneficiary"),
        ("collection", "Collection from Supplier"),
    ], string="Operation", required=True)
    method = fields.Selection([
        ("transfer", "Bank Transfer"),
        ("offset", "Accounting Offset"),
    ], string="Payment Method", required=True, default="transfer")
    amount = fields.Monetary(string="Amount", currency_field="currency_id", required=True)
    currency_id = fields.Many2one(related="request_id.currency_id", store=True)
    date = fields.Date(string="Date", required=True, default=fields.Date.context_today)
    reference = fields.Char(string="Reference / Payment No.", required=True)
    payment_id = fields.Many2one("account.payment", string="Existing Accounting Payment", check_company=True)
    evidence_attachment_ids = fields.Many2many("ir.attachment", "incentive_detail_attachment_rel", "detail_id", "attachment_id", string="Evidence")

    @api.model
    def default_get(self, fields_list):
        values = super().default_get(fields_list)
        request_id = values.get("request_id") or self.env.context.get("default_request_id")
        request = self.env["incentive.request"].browse(request_id).exists() if request_id else self.env["incentive.request"]
        if request:
            if "salesperson_id" in fields_list and not values.get("salesperson_id") and request.salesperson_id:
                values["salesperson_id"] = request.salesperson_id.id
            if "direction" in fields_list and not values.get("direction"):
                if request.state == "execution":
                    values["direction"] = "beneficiary"
                elif request.state == "pending_collection":
                    values["direction"] = "collection"
        return values

    def _check_role_for_direction(self, request, direction):
        user = self.env.user
        is_manager = user.has_group("customer_incentive_management.group_incentive_manager")
        is_treasury = user.has_group("customer_incentive_management.group_incentive_treasury") or user.has_group("customer_incentive_management.group_incentive_accounting")
        is_collection = user.has_group("customer_incentive_management.group_incentive_collection") or user.has_group("customer_incentive_management.group_incentive_accounting")
        if is_manager:
            return
        if direction == "beneficiary":
            if not is_treasury or request.state != "execution":
                raise UserError(_("Only Treasury can add or edit beneficiary payment details during In Execution."))
        elif direction == "collection":
            if not is_collection or request.state != "pending_collection":
                raise UserError(_("Only Supplier Collection can add or edit supplier collection details while Pending Collection."))
        else:
            raise UserError(_("Select a valid operation type."))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            request_id = vals.get("request_id") or self.env.context.get("default_request_id")
            request = self.env["incentive.request"].browse(request_id).exists() if request_id else self.env["incentive.request"]
            if not request:
                raise UserError(_("Select the request for this payment detail."))
            direction = vals.get("direction")
            if not direction:
                direction = "beneficiary" if request.state == "execution" else "collection" if request.state == "pending_collection" else False
                vals["direction"] = direction
            self._check_role_for_direction(request, direction)
        return super().create(vals_list)

    def write(self, vals):
        if "request_id" in vals and any(line.request_id.id != vals["request_id"] for line in self):
            raise UserError(_("A payment detail cannot be moved to another request."))
        if "direction" in vals and any(vals["direction"] != line.direction for line in self):
            raise UserError(_("The operation type cannot be changed after the payment detail is created."))
        for line in self:
            self._check_role_for_direction(line.request_id, line.direction)
        return super().write(vals)

    @api.constrains("amount")
    def _check_amount(self):
        for line in self:
            if line.amount <= 0:
                raise ValidationError(_("Payment/offset detail amount must be greater than zero."))
