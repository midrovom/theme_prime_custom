from odoo import models, fields

class HrEcOnboardingConfig(models.Model):
    _name = 'company.config'
    _description = 'Configuración de Empresas'

    name = fields.Char(string='Nombre de la Empresa', required=True)
    activo = fields.Boolean(string='Activo', default=True)

class HrEmployee(models.Model):
    _inherit = "hr.employee"

    company_config_id = fields.Many2one(
        "company.config",
        string="Empresa Afiliada",
    )

    def write(self, vals):
            old_company_config = {
                employee.id: employee.company_config_id.id
                for employee in self
            }

            result = super().write(vals)

            if "company_config_id" in vals:

                for employee in self:

                    old_value = old_company_config.get(employee.id)
                    new_value = employee.company_config_id.id

                    if old_value != new_value and new_value:

                        packages = self.env[
                            "hr.ec.onboarding.package"
                        ].sudo().search([
                            ("employee_id", "=", employee.id),
                        ])

                        if packages:

                            # Ejecutar en segundo plano
                            packages.with_delay(
                                description=(
                                    "Regenerar documentos por cambio "
                                    "de empresa afiliada"
                                )
                            ).action_generate_documents()

            return result


    # def write(self, vals):
    #         old_company_config = {
    #             employee.id: employee.company_config_id.id
    #             for employee in self
    #         }

    #         res = super().write(vals)
    #         if "company_config_id" in vals:

    #             employees_to_update = self.filtered(lambda e: old_company_config.get(e.id)
    #                 != e.company_config_id.id
    #                 and e.company_config_id
    #             )

    #             if employees_to_update:
    #                 def generate_documents():
    #                     packages = self.env["hr.ec.onboarding.package"].sudo().search([
    #                         ("employee_id", "in", employees_to_update.ids),
    #                     ])
    #                     if packages:
    #                         packages.with_context(
    #                             automatic_onboarding_generation=True,
    #                             skip_employee_company_generation=True,
    #                         ).action_generate_documents()
    #                 self.env.cr.postcommit.add(generate_documents)
    #         return res