from odoo import fields, models, tools, _


class CensusCommercialTimeline(models.Model):
    _name = "conedera.census.commercial.timeline"
    _description = "Bitácora comercial del cliente"
    _auto = False
    _order = "event_datetime desc, id desc"
    _rec_name = "title"

    partner_id = fields.Many2one("res.partner", string="Cliente", readonly=True)
    event_type = fields.Selection(
        [("visit", "Visita"), ("quotation", "Proforma / cotización")],
        string="Tipo",
        readonly=True,
    )
    event_datetime = fields.Datetime(string="Fecha", readonly=True)
    user_id = fields.Many2one("res.users", string="Vendedor", readonly=True)
    company_id = fields.Many2one("res.company", string="Compañía", readonly=True)
    title = fields.Char(string="Registro", readonly=True)
    event_state_label = fields.Char(string="Estado", readonly=True)
    visit_id = fields.Many2one("conedera.census.visit", string="Visita", readonly=True)
    sale_order_id = fields.Many2one("sale.order", string="Proforma", readonly=True)
    purchase_made = fields.Selection(
        [("yes", "Sí"), ("no", "No")], string="Compra", readonly=True
    )
    location_status = fields.Selection(
        [
            ("no_visit_gps", "Sin GPS de visita"),
            ("no_customer_gps", "Cliente sin GPS"),
            ("in_range", "Dentro de ubicación"),
            ("out_of_range", "Fuera de ubicación"),
        ],
        string="Ubicación",
        readonly=True,
    )
    amount_total = fields.Monetary(string="Total", currency_field="currency_id", readonly=True)
    currency_id = fields.Many2one("res.currency", string="Moneda", readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute(
            f"""
            CREATE OR REPLACE VIEW {self._table} AS (
                SELECT
                    (v.id * 2)::bigint AS id,
                    v.partner_id AS partner_id,
                    'visit'::varchar AS event_type,
                    v.visit_datetime AS event_datetime,
                    v.user_id AS user_id,
                    v.company_id AS company_id,
                    COALESCE(v.name, 'Visita')::varchar AS title,
                    CASE v.state
                        WHEN 'draft' THEN 'Borrador'
                        WHEN 'done' THEN 'Realizada'
                        WHEN 'cancel' THEN 'Cancelada'
                        ELSE COALESCE(v.state, '')
                    END::varchar AS event_state_label,
                    v.id AS visit_id,
                    NULL::integer AS sale_order_id,
                    v.purchase_made AS purchase_made,
                    v.location_status AS location_status,
                    0.0::numeric AS amount_total,
                    c.currency_id AS currency_id
                FROM conedera_census_visit v
                JOIN res_company c ON c.id = v.company_id

                UNION ALL

                SELECT
                    (so.id * 2 + 1)::bigint AS id,
                    so.partner_id AS partner_id,
                    'quotation'::varchar AS event_type,
                    so.date_order AS event_datetime,
                    so.user_id AS user_id,
                    so.company_id AS company_id,
                    COALESCE(so.name, 'Proforma')::varchar AS title,
                    CASE so.state
                        WHEN 'draft' THEN 'Borrador'
                        WHEN 'sent' THEN 'Enviada'
                        WHEN 'sale' THEN 'Pedido confirmado'
                        WHEN 'cancel' THEN 'Cancelada'
                        ELSE COALESCE(so.state, '')
                    END::varchar AS event_state_label,
                    NULL::integer AS visit_id,
                    so.id AS sale_order_id,
                    NULL::varchar AS purchase_made,
                    NULL::varchar AS location_status,
                    so.amount_total AS amount_total,
                    so.currency_id AS currency_id
                FROM sale_order so
                WHERE so.partner_id IS NOT NULL
            )
            """
        )

    def action_open_source(self):
        self.ensure_one()
        if self.event_type == "visit" and self.visit_id:
            return {
                "type": "ir.actions.act_window",
                "name": _("Visita comercial"),
                "res_model": "conedera.census.visit",
                "res_id": self.visit_id.id,
                "view_mode": "form",
                "views": [
                    (
                        self.env.ref("conedera_odoo_census.view_census_visit_form").id,
                        "form",
                    )
                ],
                "target": "current",
            }
        if self.event_type == "quotation" and self.sale_order_id:
            return {
                "type": "ir.actions.act_window",
                "name": _("Proforma / cotización"),
                "res_model": "sale.order",
                "res_id": self.sale_order_id.id,
                "view_mode": "form",
                "views": [(self.env.ref("sale.view_order_form").id, "form")],
                "target": "current",
            }
        return {"type": "ir.actions.act_window_close"}


class CensusProductQuoteSummary(models.Model):
    _name = "conedera.census.product.quote.summary"
    _description = "Resumen de productos proformados"
    _auto = False
    _order = "quoted_qty desc, quoted_amount desc, last_quote_date desc, id desc"
    _rec_name = "product_id"

    partner_id = fields.Many2one("res.partner", string="Cliente", readonly=True)
    product_id = fields.Many2one("product.product", string="Producto", readonly=True)
    product_tmpl_id = fields.Many2one("product.template", string="Plantilla", readonly=True)
    company_id = fields.Many2one("res.company", string="Compañía", readonly=True)
    currency_id = fields.Many2one("res.currency", string="Moneda", readonly=True)
    uom_id = fields.Many2one("uom.uom", string="UdM", readonly=True)
    quotation_count = fields.Integer(string="Proformas", readonly=True)
    quoted_qty = fields.Float(string="Cantidad proformada", readonly=True)
    quoted_amount = fields.Monetary(
        string="Importe proformado", currency_field="currency_id", readonly=True
    )
    avg_net_unit_price = fields.Monetary(
        string="Precio promedio neto", currency_field="currency_id", readonly=True
    )
    min_net_unit_price = fields.Monetary(
        string="Precio mínimo neto", currency_field="currency_id", readonly=True
    )
    max_net_unit_price = fields.Monetary(
        string="Precio máximo neto", currency_field="currency_id", readonly=True
    )
    last_quote_date = fields.Datetime(string="Última proforma", readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute(
            f"""
            CREATE OR REPLACE VIEW {self._table} AS (
                SELECT
                    MIN(sol.id)::bigint AS id,
                    so.partner_id AS partner_id,
                    sol.product_id AS product_id,
                    pp.product_tmpl_id AS product_tmpl_id,
                    so.company_id AS company_id,
                    so.currency_id AS currency_id,
                    sol.product_uom AS uom_id,
                    COUNT(DISTINCT so.id)::integer AS quotation_count,
                    SUM(sol.product_uom_qty)::double precision AS quoted_qty,
                    SUM(sol.price_subtotal)::numeric AS quoted_amount,
                    CASE
                        WHEN SUM(sol.product_uom_qty) != 0
                        THEN SUM(sol.price_subtotal) / SUM(sol.product_uom_qty)
                        ELSE 0
                    END::numeric AS avg_net_unit_price,
                    MIN(sol.price_unit * (1 - COALESCE(sol.discount, 0) / 100.0))::numeric AS min_net_unit_price,
                    MAX(sol.price_unit * (1 - COALESCE(sol.discount, 0) / 100.0))::numeric AS max_net_unit_price,
                    MAX(so.date_order) AS last_quote_date
                FROM sale_order_line sol
                JOIN sale_order so ON so.id = sol.order_id
                JOIN product_product pp ON pp.id = sol.product_id
                WHERE
                    sol.display_type IS NULL
                    AND sol.product_id IS NOT NULL
                    AND NOT sol.is_downpayment
                    AND so.partner_id IS NOT NULL
                    AND so.state != 'cancel'
                GROUP BY
                    so.partner_id,
                    sol.product_id,
                    pp.product_tmpl_id,
                    so.company_id,
                    so.currency_id,
                    sol.product_uom
            )
            """
        )

    def action_open_quote_history(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id(
            "conedera_odoo_census.action_census_product_quote_line"
        )
        action["domain"] = [
            ("partner_id", "=", self.partner_id.id),
            ("product_id", "=", self.product_id.id),
            ("company_id", "=", self.company_id.id),
            ("currency_id", "=", self.currency_id.id),
            ("uom_id", "=", self.uom_id.id),
        ]
        action["name"] = _("Historial proformado - %s") % self.product_id.display_name
        return action


class CensusProductQuoteLine(models.Model):
    _name = "conedera.census.product.quote.line"
    _description = "Detalle histórico de productos proformados"
    _auto = False
    _order = "order_date desc, order_id desc, id desc"
    _rec_name = "product_id"

    sale_line_id = fields.Many2one("sale.order.line", string="Línea origen", readonly=True)
    order_id = fields.Many2one("sale.order", string="Proforma", readonly=True)
    partner_id = fields.Many2one("res.partner", string="Cliente", readonly=True)
    product_id = fields.Many2one("product.product", string="Producto", readonly=True)
    product_tmpl_id = fields.Many2one("product.template", string="Plantilla", readonly=True)
    order_date = fields.Datetime(string="Fecha", readonly=True)
    user_id = fields.Many2one("res.users", string="Vendedor", readonly=True)
    company_id = fields.Many2one("res.company", string="Compañía", readonly=True)
    currency_id = fields.Many2one("res.currency", string="Moneda", readonly=True)
    uom_id = fields.Many2one("uom.uom", string="UdM", readonly=True)
    qty = fields.Float(string="Cantidad", readonly=True)
    price_unit = fields.Monetary(string="Precio lista", currency_field="currency_id", readonly=True)
    discount = fields.Float(string="Desc. %", readonly=True)
    net_unit_price = fields.Monetary(
        string="Precio neto", currency_field="currency_id", readonly=True
    )
    subtotal = fields.Monetary(string="Subtotal", currency_field="currency_id", readonly=True)
    state = fields.Selection(
        [
            ("draft", "Borrador"),
            ("sent", "Enviada"),
            ("sale", "Pedido confirmado"),
            ("cancel", "Cancelada"),
        ],
        string="Estado",
        readonly=True,
    )

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute(
            f"""
            CREATE OR REPLACE VIEW {self._table} AS (
                SELECT
                    sol.id::bigint AS id,
                    sol.id AS sale_line_id,
                    so.id AS order_id,
                    so.partner_id AS partner_id,
                    sol.product_id AS product_id,
                    pp.product_tmpl_id AS product_tmpl_id,
                    so.date_order AS order_date,
                    so.user_id AS user_id,
                    so.company_id AS company_id,
                    so.currency_id AS currency_id,
                    sol.product_uom AS uom_id,
                    sol.product_uom_qty::double precision AS qty,
                    sol.price_unit::numeric AS price_unit,
                    COALESCE(sol.discount, 0)::double precision AS discount,
                    (sol.price_unit * (1 - COALESCE(sol.discount, 0) / 100.0))::numeric AS net_unit_price,
                    sol.price_subtotal::numeric AS subtotal,
                    so.state AS state
                FROM sale_order_line sol
                JOIN sale_order so ON so.id = sol.order_id
                JOIN product_product pp ON pp.id = sol.product_id
                WHERE
                    sol.display_type IS NULL
                    AND sol.product_id IS NOT NULL
                    AND NOT sol.is_downpayment
                    AND so.partner_id IS NOT NULL
                    AND so.state != 'cancel'
            )
            """
        )

    def action_open_order(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Proforma / cotización"),
            "res_model": "sale.order",
            "res_id": self.order_id.id,
            "view_mode": "form",
            "views": [(self.env.ref("sale.view_order_form").id, "form")],
            "target": "current",
        }
