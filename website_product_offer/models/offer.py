# -*- coding: utf-8 -*-

import logging

from datetime import timedelta
from urllib.parse import urlencode

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


_logger = logging.getLogger(__name__)


class WebsiteSaleOffer(models.Model):
    _name = "website.sale.offer"
    _description = "Oferta comercial desde el sitio web"
    _inherit = [
        "mail.thread",
        "mail.activity.mixin",
        "portal.mixin",
    ]
    _order = "create_date desc, id desc"

    name = fields.Char(
        string="Referencia",
        required=True,
        copy=False,
        readonly=True,
        default="/",
        tracking=True,
    )
    state = fields.Selection(
        selection=[
            ("draft", "Recibida"),
            ("review", "En revisión"),
            ("counter", "Contraoferta"),
            ("converted", "Presupuesto creado"),
            ("rejected", "Rechazada"),
            ("cancelled", "Cancelada"),
        ],
        string="Estado",
        default="draft",
        required=True,
        copy=False,
        index=True,
        tracking=True,
    )
    website_id = fields.Many2one(
        comodel_name="website",
        string="Sitio web",
        required=True,
        readonly=True,
        index=True,
        ondelete="restrict",
        tracking=True,
    )
    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Compañía",
        required=True,
        readonly=True,
        index=True,
    )
    user_id = fields.Many2one(
        comodel_name="res.users",
        string="Vendedor",
        domain="[('share', '=', False)]",
        tracking=True,
    )
    partner_id = fields.Many2one(
        comodel_name="res.partner",
        string="Cliente",
        index=True,
        tracking=True,
    )
    contact_name = fields.Char(string="Contacto", required=True, tracking=True,)
    contact_email = fields.Char(string="Correo", tracking=True,)
    contact_phone = fields.Char(string="Teléfono", tracking=True,)
    company_name = fields.Char(string="Empresa",)
    pricelist_id = fields.Many2one(comodel_name="product.pricelist", string="Lista de precios", required=True, readonly=True, ondelete="restrict",)
    currency_id = fields.Many2one(related="pricelist_id.currency_id", store=True, readonly=True,)
    customer_message = fields.Text(string="Mensaje del cliente",)
    counter_message = fields.Text(string="Mensaje de contraoferta",)
    internal_note = fields.Text(string="Nota interna",)
    valid_until = fields.Date(string="Válida hasta", tracking=True,)
    source_url = fields.Char(string="Página de origen", readonly=True,)
    sale_order_id = fields.Many2one(
        comodel_name="sale.order",
        string="Presupuesto",
        readonly=True,
        copy=False,
        index=True,
        ondelete="set null",
        tracking=True,
    )
    line_ids = fields.One2many(
        comodel_name="website.sale.offer.line",
        inverse_name="offer_id",
        string="Productos",
        copy=True,
    )
    list_total = fields.Monetary(string="Total de lista", compute="_compute_amounts", currency_field="currency_id", store=True,)
    offer_total = fields.Monetary(
        string="Total ofertado",
        compute="_compute_amounts",
        currency_field="currency_id",
        store=True,
    )
    counter_price = fields.Monetary(string="Precio de contraoferta", currency_field="currency_id", tracking=True,)
    converted_price = fields.Monetary(string="Precio convertido", currency_field="currency_id", readonly=True,copy=False,)
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
    total_general = fields.Monetary(
        string="Total general",
        currency_field="currency_id",
        tracking=True,
    )

    @api.depends("line_ids.list_price", "line_ids.quantity", "line_ids.offered_price")
    def _compute_amounts(self):
        for offer in self:
            list_total = sum(line.quantity * line.list_price for line in offer.line_ids)
            offer.offer_total = sum(line.quantity * line.offered_price for line in offer.line_ids)
            offer.counter_total = list_total * (offer.counter_price / (list_total / sum(line.quantity for line in offer.line_ids))) if offer.counter_price else 0.0
            offer.requested_discount_percent = (
                ((list_total - offer.offer_total) / list_total) * 100 if list_total else 0.0
            )

    @api.constrains("counter_price")
    def _check_counter_price(self):
        for offer in self:
            if offer.counter_price < 0:
                raise ValidationError(_("El precio de contraoferta no puede ser negativo."))

    @api.constrains("line_ids")
    def _check_lines(self):
        for offer in self:
            if not offer.line_ids:
                raise ValidationError(_("La oferta debe contener al menos " "un producto."))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("partner_id") and self.env.user.partner_id:
                vals["partner_id"] = self.env.user.partner_id.id
            if vals.get("name", "/") == "/":
                vals["name"] = self.env["ir.sequence"].next_by_code("website.sale.offer") or "/"
        offers = super().create(vals_list)
        offers._portal_ensure_token()
        return offers

    def _compute_access_url(self):
        super()._compute_access_url()
        for offer in self:
            offer.access_url = f"/my/offers/{offer.id}"

    def get_portal_url(
        self,
        suffix=None,
        report_type=None,
        download=None,
        query_string=None,
        anchor=None,
    ):
        self.ensure_one()
        self._portal_ensure_token()
        url = f"/my/offers/{self.id}"
        if suffix:
            url += suffix
        params = {"access_token": self.access_token}
        if report_type:
            params["report_type"] = report_type
        if download:
            params["download"] = download
        result = f"{url}?{urlencode(params)}"
        if query_string:
            result += f"&{query_string.lstrip('?')}"
        if anchor:
            result += f"#{anchor}"
        return result

    def _check_stock_before_conversion(self):
        self.ensure_one()
        if not self.website_id.offer_limit_to_stock:
            return

        for line in self.line_ids:
            available_qty = line._current_available_qty()
            if line.quantity > available_qty:
                raise UserError(
                    _("No es posible crear el presupuesto para %(product)s: "
                    "se solicitaron %(requested)s unidades y actualmente hay %(available)s disponibles.",
                    product=line.product_id.display_name,
                    requested=line.quantity,
                    available=available_qty)
                )

    def _ensure_customer_partner(self):
        self.ensure_one()
        if self.partner_id:
            return self.partner_id

        if self.env.user.has_group("base.group_portal") and self.env.user.partner_id:
            self.sudo().partner_id = self.env.user.partner_id.id
            return self.env.user.partner_id

        Partner = self.env["res.partner"].sudo().with_company(self.company_id)
        partner = Partner.browse()
        if self.contact_email:
            matches = Partner.search(
                [("email", "=ilike", self.contact_email.strip())],
                limit=2,
            )
            if len(matches) == 1:
                partner = matches

        if not partner:
            partner_name = self.contact_name
            if self.company_name:
                partner_name = f"{self.company_name} - {self.contact_name}"
            partner = Partner.create(
                {
                    "name": partner_name,
                    "email": self.contact_email,
                    "phone": self.contact_phone,
                    "company_id": self.company_id.id,
                    "customer_rank": 1,
                }
            )
        self.sudo().partner_id = partner
        return partner

    def _quotation_action(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Presupuesto"),
            "res_model": "sale.order",
            "res_id": self.sale_order_id.id,
            "view_mode": "form",
            "target": "current",
        }

    def _convert_to_quotation(self, price_field):
        self.ensure_one()
        if self.sale_order_id:
            return self._quotation_action()

        if self.state not in ("draft", "review", "counter"):
            raise UserError(_("Esta oferta ya no puede convertirse en presupuesto."))

        if not self.line_ids:
            raise UserError(_("La oferta no contiene productos."))

        for line in self.line_ids:
            accepted_price = self.counter_price if price_field == "counter_price" else line[price_field]
            if accepted_price <= 0:
                raise UserError(
                    _("El precio acordado para %(product)s debe ser mayor que cero.",
                    product=line.product_id.display_name)
                )

        self._check_stock_before_conversion()
        partner = self._ensure_customer_partner()
        warehouse = self.website_id._get_warehouse_available()
        warehouse_id = getattr(warehouse, "id", warehouse)

        order_values = {
            "partner_id": partner.id,
            "company_id": self.company_id.id,
            "pricelist_id": self.pricelist_id.id,
            "website_id": self.website_id.id,
            "website_offer_id": self.id,
            "origin": self.name,
            "client_order_ref": self.name,
        }
        if self.user_id:
            order_values["user_id"] = self.user_id.id
        if warehouse_id:
            order_values["warehouse_id"] = warehouse_id

        SaleOrder = self.env["sale.order"].sudo().with_company(self.company_id)
        order = SaleOrder.create(order_values)
        SaleOrderLine = self.env["sale.order.line"].sudo().with_company(self.company_id)

        for line in self.line_ids:
            product = line.product_id.with_context(lang=partner.lang)
            accepted_price = self.counter_price if price_field == "counter_price" else line[price_field]

            SaleOrderLine.create({
                "order_id": order.id,
                "product_id": product.id,
                "name": product.get_product_multiline_description_sale(),
                "product_uom_qty": line.quantity,
                "product_uom": line.uom_id.id,
                "price_unit": accepted_price,
            })

        self.sudo().write({
            "sale_order_id": order.id,
            "converted_price": self.counter_price if price_field == "counter_price" else self.offer_total,
            "state": "converted",
        })

        order._portal_ensure_token()
        self.message_post(
            body=_("Oferta convertida en el presupuesto %s.", order.name),
            subtype_xmlid="mail.mt_note",
        )
        self._send_status_email("website_product_offer.mail_template_offer_converted")

        return self._quotation_action()

    def action_set_review(self):
        for offer in self:
            if offer.state == "draft":
                offer.state = "review"

    def action_accept_offer(self):
        self.ensure_one()
        return self._convert_to_quotation("offered_price")

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
        return self._convert_to_quotation("counter_price")

    def action_reject(self):
        for offer in self:
            if offer.state not in ("converted", "cancelled"):
                offer.state = "rejected"
                offer._send_status_email("website_product_offer.mail_template_offer_rejected")

    def action_cancel(self):
        for offer in self:
            if offer.state != "converted":
                offer.state = "cancelled"

    def action_customer_cancel(self):
        self.ensure_one()
        if self.state not in ("draft", "review", "counter"):
            raise UserError(_("Esta oferta ya no puede cancelarse."))
        self.state = "cancelled"

    def action_open_quotation(self):
        self.ensure_one()
        if not self.sale_order_id:
            raise UserError(_("La oferta todavía no tiene un presupuesto."))
        return self._quotation_action()

    def _send_status_email(self, template_xmlid):
        template = self.env.ref(template_xmlid, raise_if_not_found=False)
        if not template:
            return
        for offer in self:
            recipient = offer.contact_email or offer.partner_id.email
            if not recipient:
                continue
            try:
                template.sudo().send_mail(
                    offer.id,
                    force_send=False,
                    raise_exception=False,
                    email_values={"email_to": recipient},
                )
            except Exception:
                _logger.exception("No se pudo poner en cola el correo de la oferta %s", offer.name)

    @api.model
    def _default_valid_until(self, website):
        return fields.Date.context_today(self) + timedelta(days=website.offer_validity_days)
    