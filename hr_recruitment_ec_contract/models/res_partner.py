from odoo import models, fields

class Empresa(models.Model):
    _name = 'empresa.empresa'
    _description = 'Empresa'

    name = fields.Char(string="Nombre de la empresa", required=True)
    ruc = fields.Char(string="RUC", required=True)
    correo = fields.Char(string="Correo") 
    direccion = fields.Char(string="Dirección")

    representante_legal = fields.Char(string="Representante Legal", required=True)
    ruc_representante = fields.Char(string="RUC Representante", required=True)
    correo_representante = fields.Char(string="Correo Representante")

    sucursal_ids = fields.One2many( 
        'empresa.sucursal',
        'empresa_id',
        string="Sucursales"
    )
 
class Sucursal(models.Model):
    _name = 'empresa.sucursal'
    _description = 'Sucursal'

    name = fields.Char(string="Nombre de la sucursal", required=True)
    direccion = fields.Char(string="Dirección")
    ciudad = fields.Char(string="Ciudad")

    empresa_id = fields.Many2one(
        'empresa.empresa',
        string="Empresa",
        ondelete="cascade"
    )

