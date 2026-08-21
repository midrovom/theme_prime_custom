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

    # def _cart_update(self, product_id=None, line_id=None, add_qty=0, set_qty=0, **kwargs):

    #     if 'quantity' in kwargs:
    #         kwargs.pop('quantity')

    #     values = super()._cart_update(
    #         product_id=product_id,
    #         line_id=line_id,
    #         add_qty=add_qty,
    #         set_qty=set_qty,
    #         **kwargs
    #     )

    #     if self.website_id and not self.website_id._dr_has_b2b_access():
    #         for line in self.order_line:
    #             new_kwargs = dict(kwargs)  
    #             if 'quantity' in new_kwargs:
    #                 new_kwargs.pop('quantity')
    #             new_val = super()._cart_update(
    #                 product_id=line.product_id.id,
    #                 line_id=line.id,
    #                 add_qty=-1,
    #                 set_qty=0,
    #                 **new_kwargs
    #             )
    #             values.update(new_val)
    #     return values

