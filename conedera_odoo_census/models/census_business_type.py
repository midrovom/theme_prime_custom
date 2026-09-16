from odoo import fields, models


class CensusBusinessType(models.Model):
    _name = "conedera.census.business.type"
    _description = "Tipo de negocio del catastro"
    _order = "sequence, name"

    name = fields.Char(string="Tipo de negocio", required=True, translate=True)
    code = fields.Char(string="Código técnico", index=True, copy=False)
    sequence = fields.Integer(default=10)
    color = fields.Integer(string="Color")
    active = fields.Boolean(default=True)
