import base64
import io
import zipfile

from odoo import models

class HrApplicant(models.Model):
    _inherit = 'hr.applicant'

    def action_print_zip(self):
        report = self.env.ref('custom_web_hr_datos_candidatos.action_report_applicant_test')

        zip_buffer = io.BytesIO()

        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for applicant in self:
                pdf_content, _ = report._render_qweb_pdf([applicant.id])

                # Nombre limpio del archivo
                name = (applicant.partner_name or 'Candidato').replace('/', '').replace('\\', '')
                cedula = applicant.cedula or ''

                filename = f"{cedula}_{name}.pdf"
                zip_file.writestr(filename, pdf_content)

        zip_buffer.seek(0)

        attachment = self.env['ir.attachment'].create({
            'name': 'Candidatos.zip',
            'type': 'binary',
            'datas': base64.b64encode(zip_buffer.read()),
            'mimetype': 'application/zip'
        })

        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'self',
        }