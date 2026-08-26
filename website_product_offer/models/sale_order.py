from odoo import _, fields, models, api
from odoo.exceptions import UserError


class WebsiteSaleMultiOfferLine(models.Model):
    _name = "website.sale.multi.offer.line"
    _description = "Línea de oferta multiproducto"

    offer_id = fields.Many2one("website.sale.multi.offer", required=True, ondelete="cascade")
    product_id = fields.Many2one("product.product", required=True)
    uom_id = fields.Many2one(related="product_id.uom_id", store=True)
    quantity = fields.Float(required=True, digits="Product Unit of Measure")
    list_price = fields.Monetary(required=True, currency_field="currency_id")
    offered_price = fields.Monetary(required=True, currency_field="currency_id")
    counter_price = fields.Monetary(currency_field="currency_id")
    currency_id = fields.Many2one(related="offer_id.currency_id", store=True, readonly=True)

    list_total = fields.Monetary(
        compute="_compute_amounts", currency_field="currency_id", store=True
    )
    offer_total = fields.Monetary(
        compute="_compute_amounts", currency_field="currency_id", store=True
    )
    counter_total = fields.Monetary(
        compute="_compute_amounts", currency_field="currency_id", store=True
    )
    requested_discount_percent = fields.Float(
        compute="_compute_amounts", store=True, digits=(16, 2)
    )

    @api.depends("quantity", "list_price", "offered_price", "counter_price")
    def _compute_amounts(self):
        for line in self:
            line.list_total = line.quantity * line.list_price
            line.offer_total = line.quantity * line.offered_price
            line.counter_total = line.quantity * line.counter_price
            line.requested_discount_percent = (
                ((line.list_price - line.offered_price) / line.list_price) * 100
                if line.list_price else 0.0
            )
