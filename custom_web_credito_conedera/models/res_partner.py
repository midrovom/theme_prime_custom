from odoo import api, fields, models, _


class ResPartner(models.Model):
    _inherit = 'res.partner'

    conedera_credit_application_ids = fields.One2many(
        'conedera.credit.application', 'partner_id', string='Solicitudes de crédito CONEDERA')
    conedera_credit_application_count = fields.Integer(
        string='Solicitudes de crédito', compute='_compute_conedera_credit_application_count')

    def _compute_conedera_credit_application_count(self):
        Application = self.env['conedera.credit.application']
        for partner in self:
            partner.conedera_credit_application_count = Application.search_count([
                ('partner_id', '=', partner.id),
            ])

    def action_view_conedera_credit_applications(self):
        self.ensure_one()
        action = self.env.ref(
            'custom_web_credito_conedera.action_conedera_credit_applications').read()[0]
        action['domain'] = [('partner_id', '=', self.id)]
        action['context'] = {
            'default_partner_id': self.id,
            'default_company_id': self.env.company.id,
        }
        return action
