from odoo import models, fields
from odoo.exceptions import UserError


class MaintenanceReportWizard(models.TransientModel):
    _name = 'maintenance.report.wizard'
    _description = 'Wizard Acta Entrega/Devolucion'

    equipment_ids = fields.Many2many(
        'maintenance.equipment',
        string='Equipos'
    )

    entregado_por_id = fields.Many2one(
        'hr.employee',
        string='Encargado de entrega/recepción de equipos',
        required=True,
        domain="[('department_id.responsable_entrega_equipo','=',True)]"
    )

    report_type = fields.Selection([
        ('delivery', 'Entrega'),
        ('return', 'Devolución')
    ])

    def action_generate_report(self):

        equipments = self.equipment_ids

        if not equipments:
            raise UserError(
                "Debe seleccionar al menos un equipo."
            )

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

        return report.report_action(equipments)