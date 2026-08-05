from odoo import fields, models
from datetime import datetime

class HrContract(models.Model):
    _inherit = "hr.contract"

    ec_applicant_id = fields.Many2one(
        "hr.applicant",
        string="Candidato de origen",
        ondelete="set null",
        copy=False,
        index=True,
    )

    company_config_id = fields.Many2one(
        "empresa.empresa",
        related="employee_id.company_config_id",
        string="Empresa Afiliada",
        store=True,
        readonly=True,
    )

    ec_package_id = fields.Many2one(
        "hr.ec.onboarding.package",
        string="Paquete de contratación",
        ondelete="set null",
        copy=False,
    )
    ec_document_template_id = fields.Many2one(
        "hr.ec.document.template",
        string="Plantilla documental",
    )
    ec_rendered_text = fields.Html(string="Texto del contrato", sanitize=False)
    ec_attachment_id = fields.Many2one(
        "ir.attachment",
        string="PDF del contrato",
        copy=False,
        readonly=True,
    )

    calendar_entry_hour = fields.Char(
        string="Horario de entrada",
        compute="_compute_calendar_hours",
        store=False,
    )
    calendar_exit_hour = fields.Char(
        string="Horario de salida",
        compute="_compute_calendar_hours",
        store=False,
    )
    calendar_required_hours = fields.Float(
        string="Horas requeridas",
        compute="_compute_calendar_hours",
        store=False,
    )

    current_day = fields.Char(compute="_compute_current_date", store=False)
    current_month = fields.Char(compute="_compute_current_date", store=False)
    current_year = fields.Char(compute="_compute_current_date", store=False)

    _sql_constraints = [
        (
            "ec_applicant_unique",
            "UNIQUE(ec_applicant_id)",
            "Solo puede existir un contrato automático por candidato.",
        ),
    ]

    def action_print_ec_contract(self):
        self.ensure_one()
        return self.env.ref("hr_recruitment_ec_contract.action_report_ec_contract").report_action(self)

    def _compute_current_date(self):
        now = datetime.now()
        for rec in self:
            rec.current_day = now.strftime("%d")
            rec.current_month = now.strftime("%B").upper()
            rec.current_year = now.strftime("%Y")

    def _compute_calendar_hours(self):
            for rec in self:
                entry = ""
                exit = ""
                required_hours = 0.0
                if rec.resource_calendar_id:
                    if rec.resource_calendar_id.attendance_ids:
                        attendances = rec.resource_calendar_id.attendance_ids
                        entry_hour = min(attendances.mapped("hour_from"))
                        exit_hour = max(attendances.mapped("hour_to"))
                        entry = f"{entry_hour:02.0f}:00"
                        exit = f"{exit_hour:02.0f}:00"
                    # aquí tomamos el valor del campo full_time_required_hours
                    required_hours = rec.resource_calendar_id.full_time_required_hours or 0.0

                rec.calendar_entry_hour = entry
                rec.calendar_exit_hour = exit
                rec.calendar_required_hours = required_hours

    # def _compute_calendar_hours(self):
    #     for rec in self:
    #         entry = ""
    #         exit = ""
    #         if rec.resource_calendar_id and rec.resource_calendar_id.attendance_ids:
    #             attendances = rec.resource_calendar_id.attendance_ids
    #             entry_hour = min(attendances.mapped("hour_from"))
    #             exit_hour = max(attendances.mapped("hour_to"))
    #             entry = f"{entry_hour:02.0f}:00"
    #             exit = f"{exit_hour:02.0f}:00"
                
    #         rec.calendar_entry_hour = entry
    #         rec.calendar_exit_hour = exit