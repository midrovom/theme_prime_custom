from odoo import models, fields, api

# class MaintenanceEquipment(models.Model):
#     _inherit = 'maintenance.equipment'

#     entregado_por_id = fields.Many2one('hr.employee', string='Encargado de entrega/recepción de quipos', tracking=True)
#     entrega_date = fields.Date(string="Fecha de Entrega")

class Department(models.Model):
    _inherit = "hr.department"

    responsable_entrega_equipo = fields.Boolean( string="Habilita entrega",
        help="Los empleados de este departamento podrán ser designados como responsables de entrega de equipos."
    )


class IrAttachment(models.Model):
    _inherit = 'ir.attachment'

    user_has_group = fields.Boolean( string="Usuario autorizado", compute="_compute_user_has_group", store=False)

    @api.depends()
    def _compute_user_has_group(self):
        for record in self:
            record.user_has_group = self.env.user.has_group('maintenance_report.group_attachment_manager')


