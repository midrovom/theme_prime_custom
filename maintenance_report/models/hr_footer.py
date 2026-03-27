from odoo import models, fields, api

class HrFooter(models.Model):
    _name = 'hr.footer'
    _description = 'Footer'

    descripcion = fields.Text(string="Descripción")


class ReportEquipment(models.AbstractModel):
    _name = 'report.maintenance_report.report_equipment'
    _description = 'Reporte de entrega de equipo'

    @api.model
    def _get_report_values(self, docids, data=None):
        docs = self.env['maintenance.equipment'].browse(docids)
        footer = self.env['hr.footer'].search([], limit=1)  
        return {
            'doc_ids': docids,
            'doc_model': 'maintenance.equipment',
            'docs': docs,
            'footer': footer,
        }
