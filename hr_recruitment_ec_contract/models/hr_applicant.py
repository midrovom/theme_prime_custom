import logging

from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)


class HrApplicant(models.Model):
    _inherit = "hr.applicant"

    ec_contract_type_id = fields.Many2one(
        "hr.contract.type",
        string="Tipo de contrato",
        tracking=True,
        help="El módulo selecciona automáticamente una plantilla configurada para este tipo de contrato.",
    )
    contract_id = fields.Many2one(
        'hr.contract',
        string="Contrato",
        ondelete="set null"
    )
    currency_id = fields.Many2one(
        "res.currency",
        default=lambda self: self.env.company.currency_id.id,
    )
    company_config_id = fields.Many2one(
        "empresa.empresa",
        string="Empresa Afiliada",
    )
    wage = fields.Monetary(
        string="Salario",
        currency_field="currency_id",
        digits=(16, 2)
    )
    date_start = fields.Date(string="Fecha de inicio")
    date_end = fields.Date(string="Fecha fin")
    resource_calendar_id = fields.Many2one("resource.calendar")
    calendar_entry_hour = fields.Char(
            string="Horario de entrada",
            compute="_compute_calendar_hours",
            store=False,
        )
    calendar_entry_hour = fields.Char(
        string="Horario de entrada",
        compute="_compute_calendar_hours",
        store=False,
    )
    calendar_exit_hour = fields.Char(
        string="Horario de salida",
        compute="_compute_calendar_hours",
        store=False,
    )
    package_id = fields.Many2one("hr.ec.onboarding.package", string="Paquete de documentos",)

    ec_contract_template_id = fields.Many2one(
        "hr.ec.document.template",
        string="Plantilla de contrato",
        domain="[('document_type', '=', 'contract'), '|', ('company_id', '=', False), ('company_id', '=', company_id)]",
        tracking=True,
    )
    ec_contract_date_start = fields.Date(string="Inicio de contrato")
    ec_contract_date_end = fields.Date(string="Fin de contrato")
    ec_contract_wage = fields.Monetary(string="Sueldo contractual", currency_field="ec_currency_id")
    ec_currency_id = fields.Many2one(related="company_id.currency_id", readonly=True)
    ec_onboarding_package_id = fields.Many2one(
        "hr.ec.onboarding.package",
        string="Paquete de contratación",
        copy=False,
        readonly=True,
    )
    ec_generation_state = fields.Selection(related="ec_onboarding_package_id.state", string="Estado documental")
    ec_generation_message = fields.Text(related="ec_onboarding_package_id.generation_message", string="Detalle")
    sucursal_id = fields.Many2one("empresa.sucursal", string="Sucursal",
        domain="[('empresa_id', '=', company_config_id)]"
    )
    process_finalized = fields.Boolean(string="Proceso finalizado", default=False, readonly=True)

    @api.model_create_multi
    def create(self, vals_list):
        applicants = super().create(vals_list)
        applicants._ec_trigger_hired_generation()
        return applicants

    def write(self, vals):
        should_trigger = (
            "stage_id" in vals
            or "date_closed" in vals
            or any(not applicant.ec_onboarding_package_id for applicant in self)
        )
        result = super().write(vals)
        if should_trigger and not self.env.context.get("skip_ec_onboarding_generation"):
            self._ec_trigger_hired_generation()
        return result

    @api.onchange("ec_contract_type_id", "company_id")
    def _onchange_ec_contract_type_id(self):
        for applicant in self:
            if not applicant.ec_contract_type_id:
                continue
            if (
                applicant.ec_contract_template_id
                and applicant.ec_contract_template_id.contract_type_id == applicant.ec_contract_type_id
            ):
                continue
            applicant.ec_contract_template_id = self.env["hr.ec.document.template"].search([
                ("document_type", "=", "contract"),
                ("contract_type_id", "=", applicant.ec_contract_type_id.id),
                ("active", "=", True),
                "|",
                ("company_id", "=", applicant.company_id.id),
                ("company_id", "=", False),
            ], order="company_id desc, is_default desc, sequence, id", limit=1)

    def _ec_select_contract_template(self, config):
        self.ensure_one()
        if self.ec_contract_template_id:
            return self.ec_contract_template_id
        if self.ec_contract_type_id:
            template = self.env["hr.ec.document.template"].sudo().search([
                ("document_type", "=", "contract"),
                ("contract_type_id", "=", self.ec_contract_type_id.id),
                ("active", "=", True),
                "|",
                ("company_id", "=", self.company_id.id),
                ("company_id", "=", False),
            ], order="company_id desc, is_default desc, sequence, id", limit=1)
            if template:
                return template
        if (
            config.default_contract_template_id
            and (
                not self.ec_contract_type_id
                or config.default_contract_template_id.contract_type_id == self.ec_contract_type_id
            )
        ):
            return config.default_contract_template_id
        return self.env["hr.ec.document.template"].sudo().search([
            ("document_type", "=", "contract"),
            ("active", "=", True),
            "|",
            ("company_id", "=", self.company_id.id),
            ("company_id", "=", False),
        ], order="company_id desc, is_default desc, sequence, id", limit=1)

    def _ec_ensure_employee(self, config):
        self.ensure_one()
        employee = self.employee_id
        if not employee and config.auto_create_employee:
            action = self.sudo().create_employee_from_applicant()
            employee = self.env["hr.employee"].sudo().browse(action.get("res_id")).exists()
        if employee:
            vals = {}
            if self.email_from and not employee.private_email:
                vals["private_email"] = self.email_from
            if self.partner_phone and not employee.private_phone:
                vals["private_phone"] = self.partner_phone
            if self.cedula and not employee.identification_id:
                vals["identification_id"] = self.cedula
            if self.company_config_id and not employee.company_config_id:
                vals["company_config_id"] = self.company_config_id.id
            if self.sucursal_id and not employee.sucursal_id:
                vals["sucursal_id"] = self.sucursal_id.id
            if vals:
                employee.sudo().write(vals)
        return employee

    def _ec_trigger_hired_generation(self, force=False):
        if self.env.context.get("skip_ec_onboarding_generation"):
            return
        for applicant in self.filtered(lambda app: app.stage_id.hired_stage and app.active):
            config = self.env["hr.ec.onboarding.config"].get_company_config(applicant.company_id)
            if not config.auto_generate_documents and not force:
                continue
            package = applicant.ec_onboarding_package_id or self.env["hr.ec.onboarding.package"].sudo().search(
                [("applicant_id", "=", applicant.id)], limit=1
            )
            try:
                employee = applicant._ec_ensure_employee(config)
                if not employee:
                    raise ValueError(_("No fue posible crear o localizar el empleado del candidato."))
                template = applicant._ec_select_contract_template(config)
                vals = {
                    "applicant_id": applicant.id,
                    "employee_id": employee.id,
                    "contract_template_id": template.id,
                }
                if package:
                    package.sudo().write(vals)
                else:
                    package = self.env["hr.ec.onboarding.package"].sudo().create(vals)
                applicant.with_context(skip_ec_onboarding_generation=True).sudo().write({
                    "ec_onboarding_package_id": package.id,
                    "ec_contract_type_id": template.contract_type_id.id,
                    "ec_contract_template_id": template.id,
                })
                package.with_context(automatic_onboarding_generation=True).sudo().action_generate_documents()
            except Exception as exc:
                _logger.exception("Automatic EC onboarding generation failed for applicant %s", applicant.id)
                if package:
                    package.sudo().write({"state": "error", "generation_message": str(exc)})
                applicant.message_post(
                    body=_("No se pudieron generar automáticamente los documentos de contratación: %(error)s", error=str(exc))
                )

    def action_open_ec_onboarding_package(self):
        self.ensure_one()
        if not self.ec_onboarding_package_id:
            return False
        return {
            "type": "ir.actions.act_window",
            "res_model": "hr.ec.onboarding.package",
            "view_mode": "form",
            "res_id": self.ec_onboarding_package_id.id,
        }

    def action_generate_ec_onboarding_package(self):
        self.ensure_one()
        self._ec_trigger_hired_generation(force=True)
        return self.action_open_ec_onboarding_package()

    def _compute_calendar_hours(self):
            for applicant in self:
                entry = ""
                exit = ""
                calendar = applicant.resource_calendar_id
                if calendar:
                    if calendar.hora_entrada:
                        entry = f"{int(calendar.hora_entrada):02d}:00"
                    if calendar.hora_salida:
                        exit = f"{int(calendar.hora_salida):02d}:00"
                applicant.calendar_entry_hour = entry
                applicant.calendar_exit_hour = exit

    @api.onchange('company_config_id')
    def _onchange_company_config_id(self):
            self.sucursal_id = False

    def action_finalize_process(self):
        for applicant in self:
            applicant.process_finalized = True
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'hr.applicant',
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'current',
        }


