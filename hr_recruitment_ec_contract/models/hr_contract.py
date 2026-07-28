from odoo import fields, models


class HrContract(models.Model):
    _inherit = "hr.contract"

    ec_applicant_id = fields.Many2one(
        "hr.applicant",
        string="Candidato de origen",
        ondelete="set null",
        copy=False,
        index=True,
    )
    ec_package_id = fields.Many2one(
        "hr.ec.onboarding.package",
        string="Paquete de contratación",
        ondelete="set null",
        copy=False,
    )
    ec_document_template_id = fields.Many2one(
        "hr.ec.document.template",
        string="Plantilla documental",
    )
    ec_rendered_text = fields.Html(string="Texto del contrato", sanitize=False)
    ec_attachment_id = fields.Many2one(
        "ir.attachment",
        string="PDF del contrato",
        copy=False,
        readonly=True,
    )
    company_config_id = fields.Many2one(
        "company.config",
        string="Empresa"
    )

    _sql_constraints = [
        (
            "ec_applicant_unique",
            "UNIQUE(ec_applicant_id)",
            "Solo puede existir un contrato automático por candidato.",
        ),
    ]

    def action_print_ec_contract(self):
        self.ensure_one()
        return self.env.ref("hr_recruitment_ec_contract.action_report_ec_contract").report_action(self)
