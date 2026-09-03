from odoo import fields, models


class DigitalTrainingOrganization(models.Model):
    _name = "digital.training.organization"
    _description = "Empresa participante"
    _order = "name"

    name = fields.Char(string="Empresa", required=True, index=True)
    logo = fields.Image(
        string="Logo",
        max_width=1024,
        max_height=1024,
        attachment=True,
    )
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ("organization_name_unique", "unique(name)", "Ya existe una empresa con este nombre."),
    ]

