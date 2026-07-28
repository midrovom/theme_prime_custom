from odoo import models, fields

class HrEcOnboardingConfig(models.Model):
    _name = 'company.config'
    _description = 'Configuración de Empresas'

    name = fields.Char(string='Nombre de la Empresa', required=True)
    # ruc = fields.Char(string='RUC', size=13)
    # direccion = fields.Char(string='Dirección')
    # telefono = fields.Char(string='Teléfono')
    # email = fields.Char(string='Correo Electrónico')
    activo = fields.Boolean(string='Activo', default=True)
