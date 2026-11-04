from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ConederaCreditEmployerType(models.Model):
    _name = 'conedera.credit.employer.type'
    _description = 'Tipo de empleador configurable para solicitudes de crédito'
    _order = 'sequence, name, id'

    name = fields.Char(string='Tipo de empleador', required=True, translate=True)
    code = fields.Char(string='Identificador único', required=True, copy=False, index=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('conedera_credit_employer_type_code_unique', 'unique(code)',
         'Ya existe un tipo de empleador con ese identificador.'),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('code'):
                vals['code'] = self.env['ir.sequence'].next_by_code('conedera.credit.employer.type')
                if not vals['code']:
                    raise ValidationError(_('No se pudo generar el ID del tipo de empleador.'))
        return super().create(vals_list)

    def write(self, vals):
        if 'code' in vals and not self.env.context.get('credit_employer_type_migration'):
            raise ValidationError(_('El identificador del tipo de empleador no puede modificarse.'))
        return super().write(vals)
