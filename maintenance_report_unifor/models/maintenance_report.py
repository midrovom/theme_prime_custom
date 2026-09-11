from odoo import models, fields, _
from odoo.exceptions import UserError

class MaintenanceReportWizard(models.TransientModel):
    _inherit = 'maintenance.report.wizard'   # extendemos el wizard del módulo maintenance_report

    # Añadimos la opción 'uniform' al campo report_type
    report_type = fields.Selection(selection_add=[
        ('uniform', 'Uniforme'),
    ])

    def action_generate_report(self):
        equipments = self.equipment_ids

        if not equipments:
            raise UserError(_("Debe seleccionar al menos un equipo."))

        # Guardar quién entregó
        equipments.write({
            'entregado_por_id': self.entregado_por_id.id
        })

        # Selección de reporte según tipo
        if self.report_type == 'delivery':
            report = self.env.ref('maintenance_report.maintenance_equipment_report')
        elif self.report_type == 'return':
            report = self.env.ref('maintenance_report.maintenance_equipment_return_report')
        elif self.report_type == 'uniform':
            # Aquí apuntamos al reporte definido en tu módulo maintenance_report_unifor
            report = self.env.ref('maintenance_report_unifor.maintenance_equipment_uniform_report')
        else:
            raise UserError(_("Tipo de reporte no soportado."))

        return report.report_action(equipments)
