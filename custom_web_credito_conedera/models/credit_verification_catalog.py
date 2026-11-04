from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ConederaCreditVerificationZone(models.Model):
    _name = 'conedera.credit.verification.zone'
    _description = 'Zona de verificación de crédito (configurable)'
    _order = 'sequence, name, id'

    name = fields.Char(string='Zona', required=True, translate=True)
    code = fields.Char(string='ID único', readonly=True, copy=False, index=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('conedera_verification_zone_code_unique', 'unique(code)', 'El identificador de zona ya existe.'),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('code'):
                vals['code'] = self.env['ir.sequence'].next_by_code('conedera.credit.verification.zone')
                if not vals['code']:
                    raise ValidationError(_('No se pudo generar el identificador de zona.'))
        return super().create(vals_list)

    def write(self, vals):
        if 'code' in vals:
            raise ValidationError(_('El ID único de la zona no puede modificarse.'))
        return super().write(vals)


class ConederaCreditLocalCondition(models.Model):
    _name = 'conedera.credit.local.condition'
    _description = 'Estado del local (configurable)'
    _order = 'sequence, name, id'

    name = fields.Char(string='Estado del local', required=True, translate=True)
    code = fields.Char(string='ID único', readonly=True, copy=False, index=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('conedera_credit_local_condition_code_unique', 'unique(code)', 'El identificador de estado del local ya existe.'),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('code'):
                vals['code'] = self.env['ir.sequence'].next_by_code('conedera.credit.local.condition')
                if not vals['code']:
                    raise ValidationError(_('No se pudo generar el identificador del estado del local.'))
        return super().create(vals_list)

    def write(self, vals):
        if 'code' in vals:
            raise ValidationError(_('El ID único del estado del local no puede modificarse.'))
        return super().write(vals)
