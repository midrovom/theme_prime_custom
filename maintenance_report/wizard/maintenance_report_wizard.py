from odoo import models, fields

class MaintenanceReportWizard(models.TransientModel):
    _name = 'maintenance.report.wizard'
    _description = 'Wizard Acta Entrega/Devolucion'

    entregado_por_id = fields.Many2one( 'hr.employee', string='Encargado de entrega/recepción', required=True)

    report_type = fields.Selection([
        ('delivery', 'Entrega'),
        ('return', 'Devolución')
    ])

    def action_generate_report(self):

        equipment_ids = self.env.context.get('active_ids')
        equipments = self.env['maintenance.equipment'].browse(equipment_ids)

        # guardar el responsable en los equipos
        equipments.write({
            'entregado_por_id': self.entregado_por_id.id
        })

        # seleccionar reporte
        if self.report_type == 'delivery':
            report = self.env.ref(
                'maintenance_report.maintenance_equipment_report'
            )
        else:
            report = self.env.ref(
                'maintenance_report.maintenance_equipment_return_report'
            )

        return report.report_action(equipments)