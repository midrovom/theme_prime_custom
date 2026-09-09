from odoo import _, api, fields, models
from odoo.exceptions import UserError


class CommissionGoalCopyWizard(models.TransientModel):
    _name = "commission.goal.copy.wizard"
    _description = "Duplicar parámetro de comisión a otro período"

    source_model = fields.Selection(
        [
            ("commission.seller.target", "Meta de vendedor"),
            ("commission.location.target", "Meta de local"),
            ("commission.manager.goal.rule", "Gestión de administrador"),
        ],
        string="Tipo",
        required=True,
        readonly=True,
    )
    source_id = fields.Integer(required=True, readonly=True)
    source_name = fields.Char(string="Parámetro origen", readonly=True)
    source_period_id = fields.Many2one(
        "commission.period",
        string="Período origen",
        readonly=True,
    )
    destination_period_id = fields.Many2one(
        "commission.period",
        string="Período destino",
        required=True,
        domain="[('state', '=', 'draft'), ('id', '!=', source_period_id)]",
    )

    @api.model
    def _supported_models(self):
        return {
            "commission.seller.target",
            "commission.location.target",
            "commission.manager.goal.rule",
        }

    @api.model
    def _record_label(self, record):
        if record._name == "commission.seller.target":
            return _("Meta de %s") % record.seller_id.display_name
        if record._name == "commission.location.target":
            return _("Meta de %s") % record.location_id.display_name
        return record.display_name

    @api.model
    def open_for(self, record):
        if record._name not in self._supported_models():
            raise UserError(_("Este tipo de parámetro no admite duplicación controlada."))
        wizard = self.create({
            "source_model": record._name,
            "source_id": record.id,
            "source_name": self._record_label(record),
            "source_period_id": record.period_id.id,
        })
        return {
            "type": "ir.actions.act_window",
            "name": _("Duplicar a otro período"),
            "res_model": "commission.goal.copy.wizard",
            "view_mode": "form",
            "res_id": wizard.id,
            "target": "new",
        }

    def action_duplicate(self):
        self.ensure_one()
        if self.source_model not in self._supported_models():
            raise UserError(_("Tipo de parámetro no soportado."))
        if not self.destination_period_id:
            raise UserError(_("Seleccione un período destino."))
        if self.destination_period_id == self.source_period_id:
            raise UserError(_("El período destino debe ser diferente del período origen."))
        if self.destination_period_id.state != "draft":
            raise UserError(_("Solo puede duplicar parámetros hacia un período en borrador."))

        source = self.env[self.source_model].browse(self.source_id).exists()
        if not source:
            raise UserError(_("El parámetro origen ya no existe."))

        new_record = source.copy_to_period(self.destination_period_id)
        return {
            "type": "ir.actions.act_window",
            "res_model": new_record._name,
            "res_id": new_record.id,
            "view_mode": "form",
            "target": "current",
        }
