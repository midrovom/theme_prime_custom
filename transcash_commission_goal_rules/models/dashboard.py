from odoo import fields, models


class CommissionDashboardLine(models.Model):
    _name = "commission.dashboard.line"
    _description = "Analítica de comisiones"
    _order = "period_month desc, commission_recipient_id, id"

    settlement_id = fields.Many2one(
        "commission.settlement", required=True, ondelete="cascade", index=True
    )
    result_id = fields.Many2one(
        "commission.result", ondelete="cascade", index=True
    )
    period_id = fields.Many2one(
        "commission.period", required=True, ondelete="cascade", index=True
    )
    period_month = fields.Date(string="Mes", required=True, index=True)
    commission_recipient_id = fields.Many2one(
        "commission.seller", string="Comisionista", index=True, ondelete="restrict"
    )
    source_seller_id = fields.Many2one(
        "commission.seller", string="Vendedor de la venta", index=True, ondelete="restrict"
    )
    sale_id = fields.Many2one(
        "commission.sale", string="Venta", index=True, ondelete="set null"
    )
    location_id = fields.Many2one(
        "commission.location", string="Localidad", index=True, ondelete="set null"
    )
    warehouse = fields.Char(string="Almacén / bodega", index=True)
    product_line = fields.Char(string="Línea de producto", index=True)
    origin = fields.Char(string="Origen", index=True)
    client_id = fields.Many2one(
        "commission.client", string="Cliente", index=True, ondelete="set null"
    )
    client = fields.Char(string="Cliente origen", index=True)
    component = fields.Selection(
        [
            ("sales", "Ventas"),
            ("standard", "Comisión vendedor"),
            ("project", "Comisión proyecto"),
            ("management", "Gestión administrador"),
            ("liquidation", "Bono promoción"),
        ],
        string="Componente",
        required=True,
        index=True,
    )
    sale_count = fields.Integer(string="Líneas de venta", default=0)
    gross_sales = fields.Float(string="Ventas brutas", digits=(16, 4))
    target_sales = fields.Float(string="Ventas para metas", digits=(16, 4))
    commissionable_sales = fields.Float(string="Ventas comisionables", digits=(16, 4))
    commission_amount = fields.Float(string="Comisión", digits=(16, 4))
    quantity = fields.Float(string="Cantidad / m²", digits=(16, 4))
    rate = fields.Float(string="Tasa / tarifa", digits=(16, 4))
    client_excluded = fields.Boolean(string="Cliente excluido")
    counts_for_target = fields.Boolean(string="Cuenta para meta")
