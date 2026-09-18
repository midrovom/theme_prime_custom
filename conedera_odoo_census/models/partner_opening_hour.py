from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class PartnerOpeningHour(models.Model):
    _name = "conedera.partner.opening.hour"
    _description = "Horario de atención del cliente"
    _order = "day_of_week, opening_time, id"

    partner_id = fields.Many2one(
        "res.partner",
        string="Cliente",
        required=True,
        ondelete="cascade",
        index=True,
    )
    day_of_week = fields.Selection(
        [
            ("0", "Lunes"),
            ("1", "Martes"),
            ("2", "Miércoles"),
            ("3", "Jueves"),
            ("4", "Viernes"),
            ("5", "Sábado"),
            ("6", "Domingo"),
        ],
        string="Día",
        required=True,
        default="0",
    )
    opening_time = fields.Float(string="Desde", required=True, default=9.0)
    closing_time = fields.Float(string="Hasta", required=True, default=18.0)

    @api.constrains("opening_time", "closing_time")
    def _check_hours(self):
        for line in self:
            if not 0.0 <= line.opening_time < 24.0:
                raise ValidationError(_("La hora de apertura debe estar entre 00:00 y 23:59."))
            if not 0.0 < line.closing_time <= 24.0:
                raise ValidationError(_("La hora de cierre debe estar entre 00:01 y 24:00."))
            if line.closing_time <= line.opening_time:
                raise ValidationError(_("La hora de cierre debe ser posterior a la hora de apertura."))

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.context.get("census_system_write"):
            partner_ids = [vals.get("partner_id") for vals in vals_list if vals.get("partner_id")]
            self.env["res.partner"].browse(partner_ids)._check_census_master_write({"opening_hour_ids": True})
        return super().create(vals_list)

    def write(self, vals):
        if not self.env.context.get("census_system_write"):
            self.mapped("partner_id")._check_census_master_write({"opening_hour_ids": True})
        return super().write(vals)

    def unlink(self):
        if not self.env.context.get("census_system_write"):
            self.mapped("partner_id")._check_census_master_write({"opening_hour_ids": True})
        return super().unlink()
