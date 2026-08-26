from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

class WebsiteSaleOfferLine(models.Model):
    _name = "website.sale.offer.line"
    _description = "Línea de oferta comercial desde el sitio web"
    _order = "sequence, id"

    sequence = fields.Integer(default=10)

    offer_id = fields.Many2one(
        comodel_name="website.sale.offer",
        string="Oferta",
        required=True,
        ondelete="cascade",
        index=True,
    )

    product_id = fields.Many2one(
        comodel_name="product.product",
        string="Producto",
        required=True,
        ondelete="restrict",
        index=True,
    )

    product_tmpl_id = fields.Many2one(
        related="product_id.product_tmpl_id",
        string="Plantilla de producto",
        store=True,
        index=True,
    )

    uom_id = fields.Many2one(
        related="product_id.uom_id",
        string="Unidad de medida",
        store=True,
    )

    quantity = fields.Float(
        string="Cantidad",
        required=True,
        digits="Product Unit of Measure",
    )

    available_qty_snapshot = fields.Float(
        string="Stock al recibir",
        digits="Product Unit of Measure",
        readonly=True,
    )

    list_price = fields.Monetary(
        string="Precio de lista unitario",
        required=True,
        currency_field="currency_id",
    )

    offered_price = fields.Monetary(
        string="Precio unitario ofrecido",
        required=True,
        currency_field="currency_id",
    )

    counter_price = fields.Monetary(
        string="Precio de contraoferta",
        currency_field="currency_id",
    )

    converted_price = fields.Monetary(
        string="Precio convertido",
        currency_field="currency_id",
        readonly=True,
        copy=False,
    )

    list_total = fields.Monetary(
        string="Total de lista",
        compute="_compute_amounts",
        store=True,
        currency_field="currency_id",
    )

    offer_total = fields.Monetary(
        string="Total ofertado",
        compute="_compute_amounts",
        store=True,
        currency_field="currency_id",
    )

    counter_total = fields.Monetary(
        string="Total contraofertado",
        compute="_compute_amounts",
        store=True,
        currency_field="currency_id",
    )

    requested_discount_percent = fields.Float(
        string="Diferencia solicitada (%)",
        compute="_compute_amounts",
        store=True,
        digits=(16, 2),
    )

    currency_id = fields.Many2one(
        related="offer_id.currency_id",
        store=True,
        readonly=True,
    )

    @api.depends(
        "quantity",
        "list_price",
        "offered_price",
        "counter_price",
    )
    def _compute_amounts(self):
        for line in self:
            line.list_total = line.quantity * line.list_price
            line.offer_total = line.quantity * line.offered_price
            line.counter_total = line.quantity * line.counter_price

            line.requested_discount_percent = (
                ((line.list_price - line.offered_price) / line.list_price) * 100
                if line.list_price
                else 0.0
            )

    @api.constrains(
        "quantity",
        "list_price",
        "offered_price",
        "counter_price",
    )
    def _check_positive_values(self):
        for line in self:
            if line.quantity <= 0:
                raise ValidationError(
                    _("La cantidad debe ser mayor que cero.")
                )

            if (
                line.list_price < 0
                or line.offered_price <= 0
                or line.counter_price < 0
            ):
                raise ValidationError(
                    _(
                        "Los precios no pueden ser negativos "
                        "y la oferta debe ser mayor que cero."
                    )
                )