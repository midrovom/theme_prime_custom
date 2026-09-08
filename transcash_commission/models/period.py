from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class CommissionPeriod(models.Model):
    _name = "commission.period"
    _description = "Período de liquidación de comisiones"
    _order = "date_start desc, id desc"

    name = fields.Char(required=True, index=True)
    date_start = fields.Date(string="Desde", required=True, index=True)
    date_end = fields.Date(string="Hasta", required=True, index=True)
    state = fields.Selection(
        [
            ("draft", "Borrador"),
            ("calculated", "Calculado"),
            ("approved", "Aprobado"),
            ("paid", "Pagado"),
            ("cancelled", "Cancelado"),
        ],
        default="draft",
        required=True,
        index=True,
    )
    target_ids = fields.One2many("commission.seller.target", "period_id", string="Metas vendedores")
    location_target_ids = fields.One2many("commission.location.target", "period_id", string="Metas locales")
    manager_rule_ids = fields.One2many("commission.manager.rule", "period_id", string="Reglas administradores")
    liquidation_rule_ids = fields.One2many("commission.liquidation.rule", "period_id", string="Bonos liquidación")
    settlement_id = fields.Many2one("commission.settlement", string="Liquidación", readonly=True, copy=False)
    notes = fields.Text()

    @api.constrains("date_start", "date_end")
    def _check_dates(self):
        for rec in self:
            if rec.date_start and rec.date_end and rec.date_end < rec.date_start:
                raise ValidationError(_("La fecha final no puede ser anterior a la fecha inicial."))
            if rec.date_start and rec.date_end:
                overlap = self.search_count([
                    ("id", "!=", rec.id),
                    ("state", "!=", "cancelled"),
                    ("date_start", "<=", rec.date_end),
                    ("date_end", ">=", rec.date_start),
                ])
                if overlap:
                    raise ValidationError(_("No se permiten períodos de liquidación solapados."))

    def action_import_api(self):
        self.ensure_one()
        sync = self.env["commission.sync"].create({
            "name": _("Sincronización %(start)s a %(end)s") % {
                "start": self.date_start,
                "end": self.date_end,
            },
            "date_from": self.date_start,
            "date_to": self.date_end,
        })
        result = sync.run_sync()
        message = _("Importación finalizada. Creadas: %(created)s; duplicadas: %(skipped)s; errores: %(errors)s") % {
            "created": result["created"],
            "skipped": result["skipped"],
            "errors": len(result["errors"]),
        }
        if result["errors"]:
            message += "\n" + "\n".join(result["errors"][:10])
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {"title": _("Comisiones"), "message": message, "type": "warning" if result["errors"] else "success", "sticky": bool(result["errors"])},
        }

    def action_calculate(self):
        self.ensure_one()
        if self.state in ("approved", "paid"):
            raise UserError(_("No se puede recalcular un período aprobado o pagado."))
        settlement = self.env["commission.settlement"].create_or_recalculate(self)
        self.write({"state": "calculated", "settlement_id": settlement.id})
        return {
            "type": "ir.actions.act_window",
            "res_model": "commission.settlement",
            "res_id": settlement.id,
            "view_mode": "form",
        }

    def action_approve(self):
        for rec in self:
            if rec.state != "calculated" or not rec.settlement_id:
                raise UserError(_("Primero debe calcular la liquidación."))
            rec.settlement_id.state = "approved"
            rec.state = "approved"

    def action_mark_paid(self):
        for rec in self:
            if rec.state != "approved":
                raise UserError(_("Solo un período aprobado puede marcarse como pagado."))
            rec.settlement_id.state = "paid"
            rec.state = "paid"

    def action_reset_draft(self):
        for rec in self:
            if rec.state == "paid":
                raise UserError(_("Un período pagado no puede volver a borrador."))
            if rec.settlement_id:
                rec.settlement_id.state = "draft"
            rec.state = "draft"
