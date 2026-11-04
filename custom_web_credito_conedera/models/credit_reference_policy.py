from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class CreditReferencePolicy(models.Model):
    _name = 'conedera.credit.reference.policy'
    _description = 'Mínimos de referencias por empresa para solicitudes de crédito'
    _rec_name = 'company_id'

    company_id = fields.Many2one('res.company', string='Empresa', required=True,
                                 default=lambda self: self.env.company, ondelete='cascade', index=True)
    commercial_minimum = fields.Integer(string='Mínimo de referencias comerciales', default=1, required=True)
    personal_minimum = fields.Integer(string='Mínimo de referencias personales', default=1, required=True)
    bank_minimum = fields.Integer(string='Mínimo de referencias bancarias', default=1, required=True)

    _sql_constraints = [('credit_ref_policy_company_uniq', 'unique(company_id)',
                         'Ya existe una configuración de referencias para esta empresa.')]

    @api.constrains('commercial_minimum', 'personal_minimum', 'bank_minimum')
    def _check_minimums(self):
        for rec in self:
            for key in ('commercial_minimum', 'personal_minimum', 'bank_minimum'):
                if not 1 <= rec[key] <= 30:
                    raise ValidationError(_('Los mínimos deben estar entre 1 y 30.'))

    @api.model
    def minimums_for_company(self, company):
        record = self.sudo().search([('company_id', '=', company.id)], limit=1)
        return {
            'commercial': record.commercial_minimum if record else 1,
            'personal': record.personal_minimum if record else 1,
            'bank': record.bank_minimum if record else 1,
        }
