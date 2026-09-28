from odoo import models, fields, api

class ApplicantReportWizard(models.TransientModel):
    _name = 'hr.applicant.report.wizard'
    _description = 'Genera reporte de postulantes'

    applicant_ids = fields.Many2many('hr.applicant', string="Candidatos")

    @api.model
    def default_get(self, fields):
        res = super().default_get(fields)
        if self.env.context.get('active_ids'):
            res['applicant_ids'] = [(6, 0, self.env.context.get('active_ids'))]
        return res

    def action_print_pdf(self):
        return self.env.ref('custom_web_hr_datos_candidatos.action_report_applicant_test').report_action(self.applicant_ids)
