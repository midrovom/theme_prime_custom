from odoo import models, fields

class ResPartner(models.Model):
    _inherit = 'res.partner'

    representante_legal = fields.Char(string='Nombre del Representante Legal')
    ruc_representante = fields.Char(string='RUC del Representante Legal')
    correo_representante = fields.Char(string='Correo del Representante Legal')
