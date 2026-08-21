from odoo import _, fields, models
from odoo.exceptions import UserError


class SaleOrder(models.Model):
    _inherit = "sale.order"

    website_offer_id = fields.Many2one(
        comodel_name="website.sale.offer",
        string="Oferta web",
        copy=False,
        index=True,
        ondelete="set null",
    )

    def action_open_website_offer(self):
        self.ensure_one()
        if not self.website_offer_id:
            raise UserError(_("Este presupuesto no está vinculado con una oferta web."))
        return {
            "type": "ir.actions.act_window",
            "name": _("Oferta web"),
            "res_model": "website.sale.offer",
            "res_id": self.website_offer_id.id,
            "view_mode": "form",
            "target": "current",
        }
