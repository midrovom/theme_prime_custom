from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class IncentiveRequestType(models.Model):
    _name = "incentive.request.type"
    _description = "Customer Incentive Request Type"
    _order = "sequence, name"

    name = fields.Char(string="Name", required=True, translate=True)
    code = fields.Char(string="Code", required=True, index=True)
    description = fields.Text(string="Description", translate=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ("incentive_type_code_uniq", "unique(code)", "The request type code must be unique."),
    ]

    @api.constrains("code")
    def _check_code(self):
        for record in self:
            if record.code and not record.code.replace("_", "").isalnum():
                raise ValidationError(_("The code may contain only letters, numbers and underscores."))
