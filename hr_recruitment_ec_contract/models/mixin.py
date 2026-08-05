from odoo import models, fields
from datetime import datetime

class HrEcDocumentVariableMixin(models.AbstractModel):
    _name = "hr.ec.document.variable.mixin"
    _description = "Mixin para variables dinámicas de documentos laborales"

    current_day = fields.Char(compute="_compute_current_date", store=False)
    current_month = fields.Char(compute="_compute_current_date", store=False)
    current_year = fields.Char(compute="_compute_current_date", store=False)

    def _compute_current_date(self):
            meses_es = {
                "January": "ENERO",
                "February": "FEBRERO",
                "March": "MARZO",
                "April": "ABRIL",
                "May": "MAYO",
                "June": "JUNIO",
                "July": "JULIO",
                "August": "AGOSTO",
                "September": "SEPTIEMBRE",
                "October": "OCTUBRE",
                "November": "NOVIEMBRE",
                "December": "DICIEMBRE",
            }
            now = datetime.now()
            for rec in self:
                rec.current_day = now.strftime("%d")
                month_en = now.strftime("%B")
                rec.current_month = meses_es.get(month_en, month_en).upper()
                rec.current_year = now.strftime("%Y")

    company_config_id = fields.Many2one("empresa.empresa", string="Empresa Afiliada", readonly=True)
    employee_id = fields.Many2one("hr.employee", string="Empleado", readonly=True)
    ec_contract_type_id = fields.Many2one("hr.contract.type", string="Tipo de contrato", readonly=True)
    wage = fields.Float(string="Salario", readonly=True)


# Extensiones de modelos concretos para replicar variables 
class HrContract(models.Model):
    _inherit = "hr.contract"

class HrEmployee(models.Model):
    _inherit = "hr.employee"

class HrEcBenefitRequest(models.Model):
    _inherit = "hr.ec.benefit.request"

class HrEcPayrollAuthorization(models.Model):
    _inherit = "hr.ec.payroll.authorization"

class HrEcReglamentoInterno(models.Model):
    _inherit = "hr.ec.reglamento.interno"
