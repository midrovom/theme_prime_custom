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

    # Empresa
    company_config_id = fields.Many2one("empresa.empresa", string="Empresa Afiliada", readonly=True)

    # Empleado
    employee_id = fields.Many2one("hr.employee", string="Empleado", readonly=True)

    # Contrato
    ec_contract_type_id = fields.Many2one("hr.contract.type", string="Tipo de contrato", readonly=True)
    wage = fields.Float(string="Salario", readonly=True)


# Extensiones de modelos concretos
class HrContract(models.Model):
    _inherit = "hr.contract"
    _name = "hr.contract"  # mantiene el mismo nombre
    _description = "Contrato con variables dinámicas"
    _inherit = "hr.ec.document.variable.mixin"


class HrEmployee(models.Model):
    _inherit = "hr.employee"
    _name = "hr.employee"
    _description = "Empleado con variables dinámicas"
    _inherit = "hr.ec.document.variable.mixin"


class HrEcBenefitRequest(models.Model):
    _inherit = "hr.ec.benefit.request"
    _name = "hr.ec.benefit.request"
    _description = "Solicitud de acumulación de décimos con variables dinámicas"
    _inherit = "hr.ec.document.variable.mixin"


class HrEcPayrollAuthorization(models.Model):
    _inherit = "hr.ec.payroll.authorization"
    _name = "hr.ec.payroll.authorization"
    _description = "Autorización de envío de rol de pago con variables dinámicas"
    _inherit = "hr.ec.document.variable.mixin"


class HrEcReglamentoInterno(models.Model):
    _inherit = "hr.ec.reglamento.interno"
    _name = "hr.ec.reglamento.interno"
    _description = "Acta de recepción del reglamento interno con variables dinámicas"
    _inherit = "hr.ec.document.variable.mixin"
