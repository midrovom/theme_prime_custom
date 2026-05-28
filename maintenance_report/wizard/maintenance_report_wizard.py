from odoo import models, fields


class MaintenanceReportWizard(models.TransientModel):
    _name = 'maintenance.report.wizard'
    _description = 'Wizard Acta Entrega/Devolucion'

    entregado_por_id = fields.Many2one(
        'hr.employee',
        string='Encargado de entrega/recepción',
        required=True,
        domain="[('department_id.responsable_entrega_equipo','=',True)]"
    )

    report_type = fields.Selection([
        ('delivery', 'Entrega'),
        ('return', 'Devolución')
    ])

    def action_generate_report(self):

        active_ids = self.env.context.get('active_ids', [])

        # compatibilidad cuando viene solo active_id
        if not active_ids:
            active_id = self.env.context.get('active_id')
            if active_id:
                active_ids = [active_id]

        equipments = self.env['maintenance.equipment'].browse(active_ids)

        if self.report_type == 'delivery':
            report = self.env.ref(
                'maintenance_report.maintenance_equipment_report'
            )
        else:
            report = self.env.ref(
                'maintenance_report.maintenance_equipment_return_report'
            )

        return report.report_action(
            equipments.ids,
            data={
                'entregado_por_name': self.entregado_por_id.name,
                'entregado_por_ci': self.entregado_por_id.identification_id,
            }
        )