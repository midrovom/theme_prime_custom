from odoo import fields, models


class DigitalTrainingCourse(models.Model):
    _name = "digital.training.course"
    _description = "Curso de capacitación"
    _order = "name"

    name = fields.Char(string="Curso", required=True, index=True)
    code = fields.Char(string="Código")
    description = fields.Html(string="Descripción")
    default_duration_hours = fields.Float(
        string="Duración predeterminada (horas)",
        default=1.0,
        required=True,
    )
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ("course_name_unique", "unique(name)", "Ya existe un curso con este nombre."),
        (
            "course_duration_positive",
            "CHECK(default_duration_hours > 0)",
            "La duración debe ser mayor que cero.",
        ),
    ]

