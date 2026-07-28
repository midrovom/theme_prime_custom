import logging
import re
from datetime import timedelta

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class HrEcOnboardingPackage(models.Model):
    _name = "hr.ec.onboarding.package"
    _description = "Paquete de documentos de contratación"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "create_date desc, id desc"

    name = fields.Char(
        string="Número",
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _("Nuevo"),
    )
    applicant_id = fields.Many2one(
        "hr.applicant",
        string="Candidato",
        required=True,
        ondelete="cascade",
        tracking=True,
    )
    employee_id = fields.Many2one(
        "hr.employee",
        string="Empleado",
        required=True,
        ondelete="cascade",
        tracking=True,
    )
    company_id = fields.Many2one(
        "res.company",
        related="employee_id.company_id",
        store=True,
        readonly=True,
    )
    contract_id = fields.Many2one("hr.contract", string="Contrato", copy=False, readonly=True)
    benefit_request_ids = fields.One2many(
        "hr.ec.benefit.request",
        "package_id",
        string="Solicitudes de décimos",
    )

    company_config_id = fields.Many2one(
        "company.config",
        string="Empresa Configurada",
        related="contract_id.company_config_id",
        store=True,
        readonly=True,
    )
    contract_template_id = fields.Many2one(
        "hr.ec.document.template",
        string="Plantilla de contrato",
        domain="[('document_type', '=', 'contract'), '|', ('company_id', '=', False), ('company_id', '=', company_id)]",
    )
    employee_file_template_id = fields.Many2one(
        "hr.ec.document.template",
        string="Plantilla de ficha",
        domain="[('document_type', '=', 'employee_file'), '|', ('company_id', '=', False), ('company_id', '=', company_id)]",
    )
    employee_file_html = fields.Html(string="Contenido de ficha", sanitize=False)
    employee_file_attachment_id = fields.Many2one(
        "ir.attachment",
        string="PDF de ficha",
        copy=False,
        readonly=True,
    )
    attachment_ids = fields.Many2many(
        "ir.attachment",
        "hr_ec_package_attachment_rel",
        "package_id",
        "attachment_id",
        string="Archivos adjuntos",
        copy=False,
    )
    email_to = fields.Char(string="Destinatario", tracking=True)
    email_subject = fields.Char(string="Asunto", tracking=True)
    email_body_html = fields.Html(string="Cuerpo del correo", sanitize="email_outgoing")
    mail_id = fields.Many2one("mail.mail", string="Correo enviado", readonly=True, copy=False)
    state = fields.Selection(
        [
            ("draft", "Borrador"),
            ("ready", "Listo para enviar"),
            ("sent", "Enviado"),
            ("error", "Con error"),
        ],
        default="draft",
        required=True,
        tracking=True,
    )
    generated_at = fields.Datetime(string="Generado el", readonly=True)
    generation_message = fields.Text(string="Detalle de generación", readonly=True)
    document_count = fields.Integer(compute="_compute_document_count")

    _sql_constraints = [
        (
            "applicant_unique",
            "UNIQUE(applicant_id)",
            "Ya existe un paquete de contratación para este candidato.",
        ),
    ]

    @api.depends("attachment_ids")
    def _compute_document_count(self):
        for package in self:
            package.document_count = len(package.attachment_ids)

    @api.model_create_multi
    def create(self, vals_list):
        sequence = self.env["ir.sequence"]
        for vals in vals_list:
            if vals.get("name", _("Nuevo")) == _("Nuevo"):
                vals["name"] = sequence.next_by_code("hr.ec.onboarding.package") or _("Nuevo")
        packages = super().create(vals_list)
        for package in packages:
            if package.applicant_id.ec_onboarding_package_id != package:
                package.applicant_id.with_context(skip_ec_onboarding_generation=True).sudo().write({
                    "ec_onboarding_package_id": package.id,
                })
        return packages

    @api.model
    def _safe_filename(self, value):
        value = (value or "documento").strip()
        value = re.sub(r"[^A-Za-z0-9ÁÉÍÓÚÜÑáéíóúüñ._-]+", "_", value)
        return value.strip("._") or "documento"

    def _get_template(self, document_type):
        self.ensure_one()
        domain = [
            ("document_type", "=", document_type),
            ("active", "=", True),
            "|",
            ("company_id", "=", self.company_id.id),
            ("company_id", "=", False),
        ]
        return self.env["hr.ec.document.template"].sudo().search(
            domain,
            order="company_id desc, is_default desc, sequence, id",
            limit=1,
        )

    def _upsert_pdf_attachment(self, current_attachment, name, report_xmlid, record):
        self.ensure_one()
        report_service = self.env["ir.actions.report"].sudo().with_context(report_pdf_no_attachment=True)
        pdf_content, output_format = report_service._render_qweb_pdf(report_xmlid, [record.id])
        if output_format != "pdf":
            raise UserError(_("No fue posible generar el PDF %(name)s.", name=name))
        vals = {
            "name": name,
            "type": "binary",
            "raw": pdf_content,
            "mimetype": "application/pdf",
            "res_model": self._name,
            "res_id": self.id,
        }
        if current_attachment:
            current_attachment.sudo().write(vals)
            return current_attachment
        return self.env["ir.attachment"].sudo().create(vals)

    def _ensure_contract(self):
        self.ensure_one()
        applicant = self.applicant_id
        template = self.contract_template_id
        if not template:
            raise ValidationError(_("Debe configurar una plantilla de contrato para la compañía o el candidato."))

        date_start = applicant.ec_contract_date_start or applicant.availability or fields.Date.today()
        wage = applicant.ec_contract_wage or applicant.salary_proposed or template.default_wage or 0.0
        date_end = applicant.ec_contract_date_end
        if not date_end and template.duration_months:
            date_end = date_start + relativedelta(months=template.duration_months, days=-1)
        trial_date_end = date_start + timedelta(days=template.trial_days) if template.trial_days else False

        contract = self.contract_id or self.env["hr.contract"].sudo().search(
            [("ec_applicant_id", "=", applicant.id)], limit=1
        )
        vals = {
            "name": _("Contrato - %(employee)s", employee=self.employee_id.name),
            "employee_id": self.employee_id.id,
            "company_id": self.company_id.id,
            "company_config_id": self.company_config_id.id, 
            "job_id": applicant.job_id.id,
            "department_id": applicant.department_id.id,
            "date_start": date_start,
            "date_end": date_end,
            "trial_date_end": trial_date_end,
            "wage": wage,
            "contract_type_id": template.contract_type_id.id,
            "ec_applicant_id": applicant.id,
            "ec_package_id": self.id,
            "ec_document_template_id": template.id,
        }
        if contract:
            contract.write(vals)
        else:
            contract = self.env["hr.contract"].sudo().create(vals)
        contract.ec_rendered_text = template.render_document(contract)
        attachment_name = "%s.pdf" % self._safe_filename(_("Contrato_%s", self.employee_id.name))
        attachment = self._upsert_pdf_attachment(
            contract.ec_attachment_id,
            attachment_name,
            "hr_recruitment_ec_contract.action_report_ec_contract",
            contract,
        )
        contract.ec_attachment_id = attachment.id
        self.contract_id = contract.id
        return attachment

    def _ensure_benefit_request(self, benefit_type):
        self.ensure_one()
        config = self.env["hr.ec.onboarding.config"].get_company_config(self.company_id)
        enabled = (
            config.generate_thirteenth_request
            if benefit_type == "thirteenth"
            else config.generate_fourteenth_request
        )
        if not enabled:
            return self.env["ir.attachment"]

        template = self._get_template(benefit_type)
        if not template:
            raise ValidationError(_("No existe una plantilla activa para %(type)s.", type=benefit_type))
        year = (self.contract_id.date_start or fields.Date.today()).year
        request = self.env["hr.ec.benefit.request"].sudo().search([
            ("employee_id", "=", self.employee_id.id),
            ("year", "=", year),
            ("benefit_type", "=", benefit_type),
        ], limit=1)
        vals = {
            "employee_id": self.employee_id.id,
            "applicant_id": self.applicant_id.id,
            "package_id": self.id,
            "benefit_type": benefit_type,
            "year": year,
            "request_date": fields.Date.today(),
            "accumulate": True,
            "template_id": template.id,
        }
        if request:
            request.write(vals)
        else:
            request = self.env["hr.ec.benefit.request"].sudo().create(vals)
        request.rendered_text = template.render_document(request)
        label = "Decimo_Tercero" if benefit_type == "thirteenth" else "Decimo_Cuarto"
        attachment_name = "%s.pdf" % self._safe_filename("%s_%s" % (label, self.employee_id.name))
        attachment = self._upsert_pdf_attachment(
            request.attachment_id,
            attachment_name,
            "hr_recruitment_ec_contract.action_report_ec_benefit_request",
            request,
        )
        request.attachment_id = attachment.id
        return attachment

    def _ensure_employee_file(self):
        self.ensure_one()
        template = self.employee_file_template_id or self._get_template("employee_file")
        if not template:
            raise ValidationError(_("No existe una plantilla activa para la ficha del empleado."))
        self.employee_file_template_id = template.id
        self.employee_file_html = template.render_document(self.employee_id)
        attachment_name = "%s.pdf" % self._safe_filename(_("Ficha_%s", self.employee_id.name))
        attachment = self._upsert_pdf_attachment(
            self.employee_file_attachment_id,
            attachment_name,
            "hr_recruitment_ec_contract.action_report_ec_employee_file",
            self,
        )
        self.employee_file_attachment_id = attachment.id
        return attachment

    def _prepare_email_draft(self):
        self.ensure_one()
        config = self.env["hr.ec.onboarding.config"].get_company_config(self.company_id)
        contract_template = self.contract_template_id
        subject = ""
        body = ""
        if contract_template and self.contract_id:
            subject = contract_template.render_email_subject(self.contract_id)
            body = contract_template.render_email_body(self.contract_id)
        employee_name = self.employee_id.name or ""
        if not subject:
            subject = (config.email_subject or "Documentos de contratación").replace(
                "{{ employee_name }}", employee_name
            )
        if not body:
            body = (config.email_body_html or "").replace("{{ employee_name }}", employee_name)
        self.write({
            "email_to": self.employee_id.private_email or self.applicant_id.email_from or self.employee_id.work_email,
            "email_subject": subject,
            "email_body_html": body,
        })

    def action_generate_documents(self):
        for package in self:
            package.write({"state": "draft", "generation_message": False})
            attachments = self.env["ir.attachment"]
            try:
                contract_attachment = package._ensure_contract()
                if contract_attachment:
                    attachments |= contract_attachment
                for benefit_type in ("thirteenth", "fourteenth"):
                    benefit_attachment = package._ensure_benefit_request(benefit_type)
                    if benefit_attachment:
                        attachments |= benefit_attachment
                employee_attachment = package._ensure_employee_file()
                if employee_attachment:
                    attachments |= employee_attachment
                package.attachment_ids = [(6, 0, attachments.ids)]
                package._prepare_email_draft()
                package.write({
                    "state": "ready",
                    "generated_at": fields.Datetime.now(),
                    "generation_message": _("Se generaron %(count)s archivos PDF independientes.", count=len(attachments)),
                })
                package.message_post(
                    body=_("Documentos generados automáticamente: %(count)s archivos.", count=len(attachments))
                )
            except Exception as exc:
                _logger.exception("Error generating onboarding documents for package %s", package.id)
                package.write({
                    "state": "error",
                    "generation_message": str(exc),
                })
                if not self.env.context.get("automatic_onboarding_generation"):
                    raise
        return True

    def action_send_email(self):
        for package in self:
            if not package.email_to:
                raise ValidationError(_("Ingrese un correo de destinatario antes de enviar."))
            if not package.attachment_ids:
                raise ValidationError(_("El borrador no tiene documentos adjuntos."))
            email_from = package.company_id.partner_id.email_formatted or self.env.user.email_formatted
            if not email_from:
                raise ValidationError(_("Configure un correo remitente en la compañía o en el usuario actual."))
            mail = self.env["mail.mail"].sudo().create({
                "subject": package.email_subject or package.name,
                "body_html": package.email_body_html or "",
                "email_to": package.email_to,
                "email_from": email_from,
                "attachment_ids": [(6, 0, package.attachment_ids.ids)],
                "auto_delete": False,
            })
            mail.send(raise_exception=True)
            package.write({"mail_id": mail.id, "state": "sent"})
            package.message_post(body=_("Correo enviado a %(email)s.", email=package.email_to))
        return True

    def action_open_contract(self):
        self.ensure_one()
        if not self.contract_id:
            raise UserError(_("El paquete todavía no tiene contrato."))
        return {
            "type": "ir.actions.act_window",
            "res_model": "hr.contract",
            "view_mode": "form",
            "res_id": self.contract_id.id,
        }

    def action_open_employee(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "hr.employee",
            "view_mode": "form",
            "res_id": self.employee_id.id,
        }

    def action_open_requests(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Solicitudes de décimos"),
            "res_model": "hr.ec.benefit.request",
            "view_mode": "list,form",
            "domain": [("package_id", "=", self.id)],
            "context": {"default_package_id": self.id, "default_employee_id": self.employee_id.id},
        }
