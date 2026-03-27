from odoo import models, fields, api

class HrFooter(models.Model):
    _name = 'hr.footer'
    _description = 'Footer'

    descripcion = fields.Text(string="Descripción")


class ResCompany(models.Model):
    _inherit = 'res.company'

    descripcion = fields.Text(string="Footer de Reporte Entrega/Recepcion de Equipos")
