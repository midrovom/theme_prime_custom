from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

class WebsiteSaleOfferLine(models.Model):
    _name = "website.sale.offer.line"
    _description = "Línea de oferta comercial"
    _order = "sequence, id"

    offer_id = fields.Many2one(
        comodel_name="website.sale.offer",
        string="Oferta",
        required=True,
        ondelete="cascade",
        index=True,
    )

    sequence = fields.Integer(
        string="Secuencia",
        default=10,
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
        string="Plantilla",
        store=True,
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
        string="Precio de lista",
        required=True,
        readonly=True,
        currency_field="currency_id",
    )

    offered_price = fields.Monetary(
        string="Precio ofertado",
        required=True,
        currency_field="currency_id",
    )

    counter_price = fields.Monetary(
        string="Precio contraoferta",
        currency_field="currency_id",
    )

    converted_price = fields.Monetary(
        string="Precio convertido",
        readonly=True,
        copy=False,
        currency_field="currency_id",
    )

    currency_id = fields.Many2one(
        related="offer_id.currency_id",
        store=True,
        readonly=True,
    )

    list_total = fields.Monetary(
        string="Total lista",
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
        string="Total contraoferta",
        compute="_compute_amounts",
        store=True,
        currency_field="currency_id",
    )

    requested_discount_percent = fields.Float(
        string="Descuento solicitado (%)",
        compute="_compute_amounts",
        store=True,
        digits=(16, 2),
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
                (
                    (line.list_price - line.offered_price)
                    / line.list_price
                ) * 100
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

            if line.list_price < 0:
                raise ValidationError(
                    _("El precio de lista no puede ser negativo.")
                )

            if line.offered_price <= 0:
                raise ValidationError(
                    _("El precio ofertado debe ser mayor que cero.")
                )

            if line.counter_price < 0:
                raise ValidationError(
                    _("El precio de contraoferta no puede ser negativo.")
                )