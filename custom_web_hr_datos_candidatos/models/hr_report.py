import base64
import io
import zipfile
from odoo import models

class HrApplicant(models.Model):
    _inherit = 'hr.applicant'

def action_print_zip(self):
    zip_buffer = io.BytesIO()

    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for applicant in self:
            pdf_content, _ = self.env['ir.actions.report']._render_qweb_pdf(
                'custom_web_hr_datos_candidatos.report_applicant_test',
                res_ids=[applicant.id]
            )

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