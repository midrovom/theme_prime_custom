from odoo import api, fields, models, _


class ProductTemplate(models.Model):
    _inherit = "product.template"

    census_quote_currency_id = fields.Many2one(
        "res.currency", string="Moneda analítica", compute="_compute_census_quote_metrics"
    )
    census_quote_order_count = fields.Integer(
        string="Proformas", compute="_compute_census_quote_metrics"
    )
    census_quoted_qty = fields.Float(
        string="Cantidad proformada", compute="_compute_census_quote_metrics"
    )
    census_quoted_amount = fields.Monetary(
        string="Importe proformado",
        currency_field="census_quote_currency_id",
        compute="_compute_census_quote_metrics",
    )
    census_avg_quote_price = fields.Monetary(
        string="Precio promedio proformado",
        currency_field="census_quote_currency_id",
        compute="_compute_census_quote_metrics",
        help="Precio neto promedio ponderado por cantidad, convertido a la moneda de la compañía actual.",
    )
    census_last_quote_date = fields.Datetime(
        string="Última proforma", compute="_compute_census_quote_metrics"
    )

    @api.depends_context("company")
    def _compute_census_quote_metrics(self):
        company = self.env.company
        company_currency = company.currency_id
        template_ids = self.ids
        data = {
            template_id: {
                "qty": 0.0,
                "amount": 0.0,
                "orders": set(),
                "last_date": False,
            }
            for template_id in template_ids
        }
        if template_ids:
            lines = self.env["sale.order.line"].search(
                [
                    ("product_id.product_tmpl_id", "in", template_ids),
                    ("display_type", "=", False),
                    ("is_downpayment", "=", False),
                    ("order_id.state", "!=", "cancel"),
                    ("order_id.company_id", "=", company.id),
                ]
            )
            for line in lines:
                template_id = line.product_id.product_tmpl_id.id
                bucket = data[template_id]
                qty = line.product_uom_qty or 0.0
                order = line.order_id
                order_date = order.date_order or fields.Datetime.now()
                amount = order.currency_id._convert(
                    line.price_subtotal,
                    company_currency,
                    company,
                    fields.Date.to_date(order_date),
                )
                bucket["qty"] += qty
                bucket["amount"] += amount
                bucket["orders"].add(order.id)
                if not bucket["last_date"] or order_date > bucket["last_date"]:
                    bucket["last_date"] = order_date

        for template in self:
            bucket = data.get(template.id) or {}
            qty = bucket.get("qty", 0.0)
            amount = bucket.get("amount", 0.0)
            template.census_quote_currency_id = company_currency
            template.census_quote_order_count = len(bucket.get("orders", set()))
            template.census_quoted_qty = qty
            template.census_quoted_amount = amount
            template.census_avg_quote_price = amount / qty if qty else 0.0
            template.census_last_quote_date = bucket.get("last_date", False)

    def action_view_census_quote_history(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id(
            "conedera_odoo_census.action_census_product_quote_line"
        )
        action["domain"] = [
            ("product_tmpl_id", "=", self.id),
            ("company_id", "=", self.env.company.id),
        ]
        action["name"] = _("Historial proformado - %s") % self.display_name
        return action
