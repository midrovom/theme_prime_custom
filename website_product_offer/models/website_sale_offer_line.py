# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

class WebsiteSaleOfferLine(models.Model):
    _name = "website.sale.offer.line"
    _description = "Línea de oferta comercial desde el sitio web"
    _order = "sequence, id"

    sequence = fields.Integer(
        string="Secuencia",
        default=10,
    )
    offer_id = fields.Many2one(comodel_name="website.sale.offer", string="Oferta", required=True,
        index=True, ondelete="cascade",
    )
    product_id = fields.Many2one(comodel_name="product.product", string="Producto", required=True, readonly=True,
        index=True, ondelete="restrict", tracking=True,
    )
    product_tmpl_id = fields.Many2one(related="product_id.product_tmpl_id", string="Plantilla de producto", store=True, index=True,)
    uom_id = fields.Many2one(related="product_id.uom_id", string="Unidad de medida", store=True,)
    quantity = fields.Float(string="Cantidad solicitada", required=True, digits="Product Unit of Measure", tracking=True,)
    available_qty_snapshot = fields.Float(string="Stock al recibir", digits="Product Unit of Measure", readonly=True,)
    pricelist_id = fields.Many2one(comodel_name="product.pricelist", string="Lista de precios", required=True,
        readonly=True, ondelete="restrict",)
    currency_id = fields.Many2one(related="pricelist_id.currency_id", string="Moneda", store=True,readonly=True,)
    list_price = fields.Monetary(string="Precio de lista unitario", required=True, readonly=True, currency_field="currency_id",)
    offered_price = fields.Monetary(string="Precio unitario ofrecido", required=True, currency_field="currency_id", tracking=True,)
    list_total = fields.Monetary(string="Total de lista", compute="_compute_amounts", currency_field="currency_id",
        store=True,
    )
    offer_total = fields.Monetary(string="Total ofertado", compute="_compute_amounts", currency_field="currency_id",
        store=True,
    )
    requested_discount_percent = fields.Float(string="Diferencia solicitada (%)", compute="_compute_amounts", store=True,
        digits=(16, 2),
    )
    counter_price = fields.Monetary(string="Precio unitario contraoferta", currency_field="currency_id", tracking=True,)
    counter_total = fields.Monetary(string="Total contraofertado por producto", compute="_compute_amounts",
        currency_field="currency_id", store=True,)

    @api.depends("quantity", "list_price", "offered_price", "counter_price")
    def _compute_amounts(self):
        for line in self:
            line.list_total = line.quantity * line.list_price
            line.offer_total = line.quantity * line.offered_price
            line.counter_total = line.quantity * line.counter_price if line.counter_price else 0.0
            line.requested_discount_percent = (
                ((line.list_price - line.offered_price) / line.list_price) * 100
                if line.list_price else 0.0
            )

    @api.constrains("quantity", "list_price", "offered_price")
    def _check_positive_values(self):
        for line in self:
            if line.quantity <= 0:
                raise ValidationError(_("La cantidad debe ser mayor que cero."))

            if line.list_price < 0 or line.offered_price <= 0:
                raise ValidationError(
                    _("Los precios no pueden ser negativos y la oferta debe ser mayor que cero.")
                )

    def _current_available_qty(self):
        self.ensure_one()
        return self.product_tmpl_id._website_offer_available_qty(
            self.offer_id.website_id,
            self.product_id,
        )
