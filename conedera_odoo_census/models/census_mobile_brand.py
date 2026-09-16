from odoo import fields, models


class CensusMobileBrand(models.Model):
    _name = "conedera.census.mobile.brand"
    _description = "Marca de celular manejada por el cliente"
    _order = "sequence, name"

    name = fields.Char(string="Marca", required=True)
    sequence = fields.Integer(default=10)
    color = fields.Integer(string="Color")
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ("name_unique", "unique(name)", "La marca ya existe."),
    ]
