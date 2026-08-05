from odoo import models, fields, api

class HrEmployee(models.Model):
    _inherit = "hr.employee"

    company_config_id = fields.Many2one(
        "empresa.empresa",
        string="Empresa Afiliada",
    )
    sucursal_id = fields.Many2one(
        "empresa.sucursal",
        string="Sucursal",
        domain="[('empresa_id', '=', company_config_id)]"
    )

class ResourceCalendar(models.Model):
    _inherit = "resource.calendar"

    hora_entrada = fields.Float(string="Hora de entrada")
    hora_salida = fields.Float(string="Hora de salida")
