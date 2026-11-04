from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ConederaCreditBankAccountType(models.Model):
    _name = 'conedera.credit.bank.account.type'
    _description = 'Tipo configurable de cuenta bancaria de referencia'
    _order = 'sequence, name, id'

    name = fields.Char(string='Tipo de cuenta', required=True)
    code = fields.Char(string='Identificador único', required=True, copy=False, index=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    _sql_constraints = [('conedera_credit_bank_type_code_unique', 'unique(code)',
                         'El identificador del tipo de cuenta ya existe.')]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('code'):
                vals['code'] = self.env['ir.sequence'].next_by_code('conedera.credit.bank.account.type')
                if not vals['code']:
                    raise ValidationError(_('No se pudo crear el identificador del tipo de cuenta.'))
        return super().create(vals_list)

    def write(self, vals):
        if 'code' in vals and not self.env.context.get('credit_bank_type_migration'):
            raise ValidationError(_('El identificador del tipo de cuenta no puede modificarse.'))
        return super().write(vals)
