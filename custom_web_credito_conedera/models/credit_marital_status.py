from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ConederaCreditMaritalStatus(models.Model):
    _name = 'conedera.credit.marital.status'
    _description = 'Estado civil configurable para solicitudes de crédito'
    _order = 'sequence, name, id'

    name = fields.Char(string='Estado civil', required=True, translate=True)
    code = fields.Char(string='ID único', readonly=True, copy=False, index=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    requires_spouse = fields.Boolean(string='Requiere datos del cónyuge', default=False, help='Al seleccionar este estado civil, el portal mostrará y exigirá nombres, documento y profesión del cónyuge.')

    _sql_constraints = [
        ('credit_marital_code_uniq', 'unique(code)', 'El ID del estado civil ya está registrado.'),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('code'):
                vals['code'] = self.env['ir.sequence'].next_by_code('conedera.credit.marital.status')
                if not vals['code']:
                    raise ValidationError(_('No se pudo generar el ID del estado civil.'))
        return super().create(vals_list)

    def write(self, vals):
        if 'code' in vals and not self.env.context.get('credit_identifier_migration'):
            raise ValidationError(_('El ID del estado civil es permanente.'))
        return super().write(vals)
