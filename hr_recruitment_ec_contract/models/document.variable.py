from odoo import models, fields


class HrEcDocumentVariable(models.Model):
    _name = "hr.ec.document.variable"
    _description = "Variables dinámicas documentos laborales"
    _order = "sequence, id"

    name = fields.Char(
        string="Nombre visible",
        required=True
    )

    key = fields.Char(
        string="Código variable",
        required=True,
        help="Código que utilizará el usuario en la plantilla"
    )

    expression = fields.Char(
        string="Expresión interna",
        required=True,
        help="Campo real QWeb"
    )

    sequence = fields.Integer(
        default=10
    )

    active = fields.Boolean(
        default=True
    )