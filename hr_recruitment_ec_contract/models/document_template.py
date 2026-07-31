from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from lxml import etree

class HrEcDocumentTemplate(models.Model):
    _name = "hr.ec.document.template"
    _description = "Plantilla de documento de contratación EC"
    _inherit = ["mail.render.mixin"]
    _order = "document_type, sequence, name"

    name = fields.Char(string="Nombre", required=True, translate=True)
    active = fields.Boolean(default=True)
    sequence = fields.Integer(default=10)
    company_id = fields.Many2one(
        "res.company",
        string="Compañía",
        help="Déjelo vacío para que la plantilla pueda utilizarse en todas las compañías.",
    )

    variable_ids = fields.Many2many(
        "hr.ec.document.variable",
        string="Variables disponibles",
        compute="_compute_variable_ids",
        readonly=True,
    )

    document_type = fields.Selection(
        [
            ("contract", "Contrato"),
            ("thirteenth", "Solicitud de acumulación de décimo tercero"),
            ("fourteenth", "Solicitud de acumulación de décimo cuarto"),
            ("employee_file", "Ficha del empleado"),
            ("payroll_email", "Autorización envío rol de pago"),
            ("reglamento_interno", "Acta Reglamento Interno"),  # NUEVO

        ],
        string="Tipo de documento",
        required=True,
        default="contract",
    )
    contract_type_id = fields.Many2one(
        "hr.contract.type",
        string="Tipo de contrato",
        help="Se usa para seleccionar el texto correcto y crear el contrato en Odoo.",
    )
    is_default = fields.Boolean(
        string="Predeterminada",
        help="Cuando no se selecciona otra plantilla, se utiliza la predeterminada compatible con la compañía.",
    )
    body_html = fields.Html(
        string="Texto del documento",
        required=True,
        render_engine="qweb",
        render_options={"post_process": False},
        sanitize="email_outgoing",
        translate=True,
    )
    email_subject = fields.Char(
        string="Asunto sugerido del correo",
        render_engine="inline_template",
        translate=True,
    )
    email_body_html = fields.Html(
        string="Cuerpo sugerido del correo",
        render_engine="qweb",
        render_options={"post_process": True},
        sanitize="email_outgoing",
        translate=True,
    )
    default_wage = fields.Monetary(string="Sueldo mensual predeterminado")
    currency_id = fields.Many2one(
        "res.currency",
        related="company_id.currency_id",
        readonly=True,
    )
    duration_months = fields.Integer(
        string="Duración en meses",
        help="Si es mayor que cero, la fecha final se calcula automáticamente.",
    )
    trial_days = fields.Integer(string="Días de prueba")

    render_model = fields.Char(compute="_compute_render_model")

    @api.depends("document_type")
    def _compute_render_model(self):
        model_by_type = {
            "contract": "hr.contract",
            "thirteenth": "hr.ec.benefit.request",
            "fourteenth": "hr.ec.benefit.request",
            "employee_file": "hr.employee",
            "payroll_email": "hr.ec.payroll.authorization",
            "reglamento_interno": "hr.ec.reglamento.interno",  # NUEVO
        }
        for template in self:
            template.render_model = model_by_type.get(template.document_type)

    @api.constrains("document_type", "contract_type_id")
    def _check_contract_type(self):
        for template in self:
            if template.document_type == "contract" and not template.contract_type_id:
                raise ValidationError(_("Las plantillas de contrato deben tener un tipo de contrato."))
            if template.document_type != "contract" and template.contract_type_id:
                raise ValidationError(_("El tipo de contrato solo aplica a plantillas de contrato."))

    @api.constrains("duration_months", "trial_days")
    def _check_positive_values(self):
        for template in self:
            if template.duration_months < 0 or template.trial_days < 0:
                raise ValidationError(_("La duración y los días de prueba no pueden ser negativos."))

    # CONVERSION VARIABLES USUARIO -> QWEB
    def _replace_dynamic_variables(self, html):
        """
        Convierte:
        {{DIA_ACTUAL}}
        en:
        <t t-out="object.current_day"/>
        """
        if not html:
            return html
        variables = self.env[
            "hr.ec.document.variable"
        ].search(
            [
                ("active", "=", True)
            ]
        )
        for variable in variables:

            html = html.replace(
                "{{%s}}" % variable.key,
                '<t t-out="%s"/>' % variable.expression
            )
        return html

    def render_document(self, record):
        self.ensure_one()

        if not record or record._name != self.render_model:
            raise ValidationError(
                _("La plantilla %(template)s requiere un registro del modelo %(model)s.",
                template=self.display_name,
                model=self.render_model)
            )

        html = self.body_html or ""
        html = self._replace_dynamic_variables(html)

        if not html.strip():
            return ""

        try:
            qweb_template = etree.fromstring(
                ("<t>%s</t>" % html).encode("utf-8")
            )
        except Exception as e:
            raise ValidationError(
                _("Error procesando la plantilla HTML: %s") % e
            )

        return self.env["ir.qweb"]._render(
            qweb_template,
            {
                "object": record,
            }
        )

    # def render_document(self, record):
    #     self.ensure_one()
    #     if not record or record._name != self.render_model:
    #         raise ValidationError(
    #             _("La plantilla %(template)s requiere un registro del modelo %(model)s.",
    #               template=self.display_name, model=self.render_model)
    #         )
    #     return self._render_field("body_html", [record.id]).get(record.id, "")

    def render_email_subject(self, record):
        self.ensure_one()
        if not self.email_subject:
            return ""
        return self._render_field("email_subject", [record.id]).get(record.id, "")

    def render_email_body(self, record):
        self.ensure_one()
        if not self.email_body_html:
            return ""
        return self._render_field("email_body_html", [record.id]).get(record.id, "")

    @api.depends()
    def _compute_variable_ids(self):
        variables = self.env["hr.ec.document.variable"].search([
            ("active", "=", True)
        ])

        for record in self:
            record.variable_ids = variables