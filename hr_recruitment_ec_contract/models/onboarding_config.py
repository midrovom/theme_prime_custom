from odoo import api, fields, models


class HrEcOnboardingConfig(models.Model):
    _name = "hr.ec.onboarding.config"
    _description = "Configuración de contratación EC"
    _rec_name = "company_id"

    company_id = fields.Many2one(
        "res.company",
        string="Compañía",
        required=True,
        default=lambda self: self.env.company,
        ondelete="cascade",
    )
    contract_id = fields.Many2one("hr.contract", string="Contrato")
    company_config_id = fields.Many2one(
        "company.config",
        string="Empresa",
        related="contract_id.company_config_id",
        store=True,
        readonly=True,
    )
    auto_create_employee = fields.Boolean(
        string="Crear empleado automáticamente",
        default=True,
        help="Si el candidato aún no tiene empleado, se crea al llegar a una etapa marcada como Contratado.",
    )
    auto_generate_documents = fields.Boolean(
        string="Generar documentos automáticamente",
        default=True,
    )
    default_contract_template_id = fields.Many2one(
        "hr.ec.document.template",
        string="Plantilla de contrato predeterminada",
        domain="[('document_type', '=', 'contract'), '|', ('company_id', '=', False), ('company_id', '=', company_id)]",
    )
    generate_thirteenth_request = fields.Boolean(
        string="Generar solicitud de décimo tercero",
        default=True,
    )
    generate_fourteenth_request = fields.Boolean(
        string="Generar solicitud de décimo cuarto",
        default=True,
    )
    email_subject = fields.Char(
        string="Asunto predeterminado",
        default="Documentos de contratación - {{ employee_name }}",
    )
    email_body_html = fields.Html(
        string="Cuerpo predeterminado",
        default=(
            "<p>Estimado/a {{ employee_name }},</p>"
            "<p>Adjuntamos sus documentos de contratación para revisión y firma.</p>"
            "<p>Saludos cordiales.</p>"
        ),
        sanitize="email_outgoing",
    )

    _sql_constraints = [
        (
            "company_unique",
            "UNIQUE(company_id)",
            "Solo puede existir una configuración de contratación por compañía.",
        ),
    ]

    @api.model
    def get_company_config(self, company):
        config = self.sudo().search([("company_id", "=", company.id)], limit=1)
        if config:
            return config
        default_template = self.env["hr.ec.document.template"].sudo().search(
            [
                ("document_type", "=", "contract"),
                ("is_default", "=", True),
                "|",
                ("company_id", "=", company.id),
                ("company_id", "=", False),
            ],
            order="company_id desc, sequence, id",
            limit=1,
        )
        return self.sudo().create({
            "company_id": company.id,
            "default_contract_template_id": default_template.id,
        })
