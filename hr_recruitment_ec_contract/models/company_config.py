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
        related="contract_id.company_config_id",
        string="Empresa Configurada",
        readonly=True,
        store=True,
    )