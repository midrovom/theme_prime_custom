from odoo import api, fields, models, _

class HrEcPayrollAuthorization(models.Model):
    _name = "hr.ec.payroll.authorization"
    _description = "Autorización de envío de rol de pago"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "request_date desc, id desc"

    name = fields.Char(
            string="Número",
            required=True,
            copy=False,
            readonly=True,
            default=lambda self: _("Nuevo"),
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

    company_config_id = fields.Many2one(
            "empresa.empresa",
            related="employee_id.company_config_id",
            string="Empresa Afiliada",
            store=True,
            readonly=True,
        )

    request_date = fields.Date(string="Fecha de solicitud", required=True,
        default=fields.Date.today
    )

    current_day = fields.Char(compute="_compute_current_date", store=False)
    current_month = fields.Char(compute="_compute_current_date", store=False)
    current_year = fields.Char(compute="_compute_current_date", store=False)
    applicant_id = fields.Many2one("hr.applicant", string="Candidato", ondelete="set null")
    package_id = fields.Many2one("hr.ec.onboarding.package", string="Paquete", ondelete="set null")
    template_id = fields.Many2one("hr.ec.document.template", string="Plantilla")
    rendered_text = fields.Html(string="Texto generado", sanitize=False)
    attachment_id = fields.Many2one("ir.attachment", string="PDF generado", copy=False, readonly=True)
    state = fields.Selection(
        [
            ("draft", "Borrador"),
            ("signed", "Firmada"),
            ("cancel", "Cancelada"),
        ],
        default="draft",
        required=True,
        tracking=True,
    )

    @api.model_create_multi
    def create(self, vals_list):
            sequence = self.env["ir.sequence"]
            for vals in vals_list:
                if vals.get("name", _("Nuevo")) == _("Nuevo"):
                    vals["name"] = sequence.next_by_code("hr.ec.payroll.authorization") or _("Nuevo")
            return super().create(vals_list)

    def action_print_request(self):
        self.ensure_one()
        return self.env.ref("hr_recruitment_ec_contract.action_report_payroll_email_authorization").report_action(self)

