from odoo import models, fields
from datetime import datetime

class HrEcDocumentVariableMixin(models.AbstractModel):
    _name = "hr.ec.document.variable.mixin"
    _description = "Mixin para variables dinámicas de documentos laborales"

    # Fecha actual
    current_day = fields.Char(compute="_compute_current_date", store=False)
    current_month = fields.Char(compute="_compute_current_date", store=False)
    current_year = fields.Char(compute="_compute_current_date", store=False)

    def _compute_current_date(self):
        now = datetime.now()
        for rec in self:
            rec.current_day = now.strftime("%d")
            rec.current_month = now.strftime("%B").upper()
            rec.current_year = now.strftime("%Y")

    # Empresa (relación con configuración de empresa)
    company_config_id = fields.Many2one(
        "empresa.empresa",
        string="Empresa Afiliada",
        readonly=True,
    )

    # Empleado
    employee_id = fields.Many2one(
        "hr.employee",
        string="Empleado",
        readonly=True,
    )

    # Contrato
    ec_contract_type_id = fields.Many2one(
        "hr.contract.type",
        string="Tipo de contrato",
        readonly=True,
    )
    wage = fields.Float(string="Salario", readonly=True)


# Ahora heredas el mixin en todos los modelos que se renderizan:

class HrContract(models.Model):
    _inherit = ["hr.contract", "hr.ec.document.variable.mixin"]

class HrEmployee(models.Model):
    _inherit = ["hr.employee", "hr.ec.document.variable.mixin"]

class HrEcBenefitRequest(models.Model):
    _inherit = ["hr.ec.benefit.request", "hr.ec.document.variable.mixin"]

class HrEcPayrollAuthorization(models.Model):
    _inherit = ["hr.ec.payroll.authorization", "hr.ec.document.variable.mixin"]

class HrEcReglamentoInterno(models.Model):
    _inherit = ["hr.ec.reglamento.interno", "hr.ec.document.variable.mixin"]
