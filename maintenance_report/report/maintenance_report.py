from odoo import models


class ReportEquipment(models.AbstractModel):
    _name = 'report.maintenance_report.report_equipment'

    def _get_report_values(self, docids, data=None):

        docs = self.env['maintenance.equipment'].browse(docids)

        return {
            'doc_ids': docids,
            'doc_model': 'maintenance.equipment',
            'docs': docs,
            'data': data or {},
        }


class ReportEquipmentReturn(models.AbstractModel):
    _name = 'report.maintenance_report.report_equipment_return'

    def _get_report_values(self, docids, data=None):

        docs = self.env['maintenance.equipment'].browse(docids)

        return {
            'doc_ids': docids,
            'doc_model': 'maintenance.equipment',
            'docs': docs,
            'data': data or {},
        }