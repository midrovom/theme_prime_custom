from odoo import models, fields

class HrEcOnboardingConfig(models.Model):
    _name = 'company.config'
    _description = 'Configuración de Empresas'

    name = fields.Char(string='Nombre de la Empresa', required=True)
    activo = fields.Boolean(string='Activo', default=True)
    ruc_empresa = fields.Char(string='RUC de la Empresa', required=True)
    representante_legal = fields.Char(string='Nombre del Representante Legal')
    ruc_representante = fields.Char(string='RUC del Representante Legal')
    correo_representante = fields.Char(string='Correo del Representante Legal')

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

        res = super().write(vals)

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

                        packages.with_context(
                            automatic_onboarding_generation=True
                        ).action_generate_documents()
        return res
    