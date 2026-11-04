from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ConederaCreditHousingType(models.Model):
    _name = 'conedera.credit.housing.type'
    _description = 'Tipo de vivienda configurable para solicitudes de crédito'
    _order = 'sequence, name, id'

    name = fields.Char(string='Tipo de vivienda', required=True, translate=True)
    code = fields.Char(string='ID único', readonly=True, copy=False, index=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('credit_housing_code_uniq', 'unique(code)', 'El ID del tipo de vivienda ya está registrado.'),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('code'):
                vals['code'] = self.env['ir.sequence'].next_by_code('conedera.credit.housing.type')
                if not vals['code']:
                    raise ValidationError(_('No se pudo generar el ID del tipo de vivienda.'))
        return super().create(vals_list)

    def write(self, vals):
        if 'code' in vals and not self.env.context.get('credit_identifier_migration'):
            raise ValidationError(_('El ID del tipo de vivienda es permanente.'))
        return super().write(vals)
