from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

class WebsiteSaleOfferLine(models.Model):
    _name = "website.sale.offer.line"
    _description = "Línea de producto en oferta comercial"

    offer_id = fields.Many2one(
        comodel_name="website.sale.offer",
        string="Oferta",
        required=True,
        ondelete="cascade",
    )

    product_id = fields.Many2one(
        comodel_name="product.product",
        string="Producto",
        required=True,
        index=True,
        ondelete="restrict",
        tracking=True,
    )
    product_tmpl_id = fields.Many2one(
        related="product_id.product_tmpl_id",
        store=True,
        readonly=True,
    )
    uom_id = fields.Many2one(
        related="product_id.uom_id",
        store=True,
        readonly=True,
    )
    quantity = fields.Float(
        string="Cantidad solicitada",
        required=True,
        digits="Product Unit of Measure",
        tracking=True,
    )
    available_qty_snapshot = fields.Float(
        string="Stock al recibir",
        digits="Product Unit of Measure",
        readonly=True,
    )
    pricelist_id = fields.Many2one(
        comodel_name="product.pricelist",
        string="Lista de precios",
        required=True,
        readonly=True,
        ondelete="restrict",
    )
    currency_id = fields.Many2one(
        related="pricelist_id.currency_id",
        store=True,
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
        tracking=True,
    )
    counter_price = fields.Monetary(
        string="Precio de contraoferta",
        currency_field="currency_id",
        tracking=True,
    )
    list_total = fields.Monetary(
        string="Total de lista",
        compute="_compute_amounts",
        currency_field="currency_id",
        store=True,
    )
    offer_total = fields.Monetary(
        string="Total ofertado",
        compute="_compute_amounts",
        currency_field="currency_id",
        store=True,
    )
    counter_total = fields.Monetary(
        string="Total contraofertado",
        compute="_compute_amounts",
        currency_field="currency_id",
        store=True,
    )
    requested_discount_percent = fields.Float(
        string="Diferencia solicitada (%)",
        compute="_compute_amounts",
        store=True,
        digits=(16, 2),
    )

    def action_send_counter(self):
        self.ensure_one()
        if self.state not in ("draft", "review", "counter"):
            raise UserError(_("Esta oferta ya no admite una contraoferta."))
        if self.counter_price <= 0:
            raise UserError(_("Ingrese un precio de contraoferta mayor que cero."))
        self.state = "counter"
        self.message_post(
            body=_("Se envió una contraoferta de %(price)s por unidad.", price=self.counter_price),
            subtype_xmlid="mail.mt_note",
        )
        self._send_status_email("website_product_offer.mail_template_offer_counter")

    def action_customer_accept_counter(self):
        self.ensure_one()
        if self.state != "counter" or self.counter_price <= 0:
            raise UserError(_("La contraoferta ya no está disponible."))
        if self.valid_until and self.valid_until < fields.Date.context_today(self):
            raise UserError(_("La contraoferta venció. Solicita una nueva revisión comercial."))
        return self._convert_to_quotation(self.counter_price)

    @api.depends("quantity", "list_price", "offered_price", "counter_price")
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

    @api.constrains("quantity", "list_price", "offered_price", "counter_price")
    def _check_positive_values(self):
        for line in self:
            if line.quantity <= 0:
                raise ValidationError(_("La cantidad debe ser mayor que cero."))
            if line.list_price < 0 or line.offered_price <= 0 or line.counter_price < 0:
                raise ValidationError(
                    _("Los precios no pueden ser negativos y la oferta debe ser mayor que cero.")
                )

