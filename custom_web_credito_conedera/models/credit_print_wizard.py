from odoo import fields, models, _
from odoo.exceptions import AccessError, UserError


class ConederaCreditPrintWizard(models.TransientModel):
    _name = 'conedera.credit.print.wizard'
    _description = 'Seleccionar PDF de crédito'

    application_id = fields.Many2one(
        'conedera.credit.application', string='Solicitud', required=True, readonly=True)
    report_choice = fields.Selection([
        ('application', 'Solo solicitud de crédito'),
        ('verification', 'Solo verificación de ubicación del negocio'),
        ('both', 'Solicitud y verificación en un solo PDF'),
    ], required=True, default='both', string='Documento a descargar')

    def action_download(self):
        self.ensure_one()
        if not self.application_id.exists():
            raise UserError(_('La solicitud ya no existe.'))
        # Check ACL and multi-company record rules before generating a report.
        self.application_id.check_access('read')
        report_ids = {
            'application': 'action_report_credit_application_only',
            'verification': 'action_report_credit_verification_only',
            'both': 'action_report_credit_application',
        }
        if self.report_choice not in report_ids:
            raise UserError(_('Seleccione un documento válido.'))
        report = self.env.ref('custom_web_credito_conedera.' + report_ids[self.report_choice])
        return report.report_action(self.application_id)
