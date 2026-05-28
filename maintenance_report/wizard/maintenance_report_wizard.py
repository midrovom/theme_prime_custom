from odoo import models, fields
from odoo.exceptions import UserError


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

        equipment_ids = (
            self.env.context.get('active_ids')
            or self.env.context.get('active_id')
        )

        # cuando viene un solo id
        if isinstance(equipment_ids, int):
            equipment_ids = [equipment_ids]

        # validación
        if not equipment_ids:
            raise UserError(
                "Debe seleccionar al menos un equipo."
            )

        equipments = self.env['maintenance.equipment'].browse(
            equipment_ids
        )

        # guardar encargado en equipos
        equipments.write({
            'entregado_por_id': self.entregado_por_id.id
        })

        if self.report_type == 'delivery':
            report = self.env.ref(
                'maintenance_report.maintenance_equipment_report'
            )
        else:
            report = self.env.ref(
                'maintenance_report.maintenance_equipment_return_report'
            )

        return report.report_action(
            equipments,
            data={
                'entregado_por_name': self.entregado_por_id.name,
                'entregado_por_ci': self.entregado_por_id.identification_id,
            }
        )