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
        res = super().write(vals)

        if "company_config_id" in vals:
            for package in self:
                if package.employee_id:
                    package.employee_id.company_config_id = package.company_config_id.id

        return res