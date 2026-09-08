from odoo import api, fields, models
from odoo.exceptions import ValidationError


class CommissionSellerTarget(models.Model):
    _name = "commission.seller.target"
    _description = "Meta de vendedor por período"
    _order = "period_id, seller_id"

    period_id = fields.Many2one("commission.period", required=True, ondelete="cascade", index=True)
    seller_id = fields.Many2one("commission.seller", required=True, ondelete="cascade", index=True)
    location_id = fields.Many2one(
        "commission.location",
        string="Localidad",
        help="Opcional. Si se informa, la meta se calcula solo con ventas de esta localidad.",
    )
    target_amount = fields.Float(string="Meta de ventas", required=True, digits=(16, 4))
    basis = fields.Selection(
        [("net", "Total neto"), ("price", "Total precio"), ("margin", "Utilidad")],
        default="net",
        required=True,
    )
    tier_ids = fields.One2many("commission.seller.target.tier", "target_id", string="Rangos")
    active = fields.Boolean(default=True)

    _sql_constraints = [
        (
            "seller_target_unique",
            "unique(period_id, seller_id, location_id)",
            "Ya existe una meta para ese vendedor, período y localidad.",
        )
    ]


    @api.constrains("period_id", "seller_id", "location_id")
    def _check_unique_target(self):
        for rec in self:
            domain = [("id", "!=", rec.id), ("period_id", "=", rec.period_id.id), ("seller_id", "=", rec.seller_id.id)]
            domain.append(("location_id", "=", rec.location_id.id if rec.location_id else False))
            if self.search_count(domain):
                raise ValidationError("Ya existe una meta para ese vendedor, período y localidad.")

    @api.constrains("target_amount")
    def _check_target_amount(self):
        for rec in self:
            if rec.target_amount <= 0:
                raise ValidationError("La meta de ventas debe ser mayor que cero.")


class CommissionSellerTargetTier(models.Model):
    _name = "commission.seller.target.tier"
    _description = "Rango de comisión de vendedor"
    _order = "min_achievement asc"

    target_id = fields.Many2one("commission.seller.target", required=True, ondelete="cascade")
    min_achievement = fields.Float(
        string="Cumplimiento mínimo (%)",
        required=True,
        help="Ej.: 80 significa que el vendedor debe alcanzar al menos 80% de la meta.",
    )
    max_achievement = fields.Float(
        string="Cumplimiento máximo (%)",
        help="Vacío o 0 significa sin límite superior.",
    )
    commission_percent = fields.Float(string="Comisión (%)", required=True, digits=(16, 4))

    @api.constrains("min_achievement", "max_achievement", "commission_percent")
    def _check_tier(self):
        for rec in self:
            if rec.min_achievement < 0 or rec.commission_percent < 0:
                raise ValidationError("Los porcentajes no pueden ser negativos.")
            if rec.max_achievement and rec.max_achievement < rec.min_achievement:
                raise ValidationError("El cumplimiento máximo no puede ser menor al mínimo.")


class CommissionLocationTarget(models.Model):
    _name = "commission.location.target"
    _description = "Meta de localidad por período"
    _order = "period_id, location_id"

    period_id = fields.Many2one("commission.period", required=True, ondelete="cascade", index=True)
    location_id = fields.Many2one("commission.location", required=True, ondelete="cascade", index=True)
    target_amount = fields.Float(string="Meta de ventas", required=True, digits=(16, 4))
    basis = fields.Selection(
        [("net", "Total neto"), ("price", "Total precio"), ("margin", "Utilidad")],
        default="net",
        required=True,
    )
    required_achievement = fields.Float(
        string="Cumplimiento requerido (%)",
        default=100.0,
        required=True,
        help="Porcentaje de meta local requerido para habilitar la comisión de gestión del administrador.",
    )

    _sql_constraints = [
        (
            "location_target_unique",
            "unique(period_id, location_id)",
            "Ya existe una meta para esa localidad y período.",
        )
    ]


class CommissionManagerRule(models.Model):
    _name = "commission.manager.rule"
    _description = "Regla de comisión por gestión de administrador"
    _order = "period_id, manager_id, min_seller_sales"

    period_id = fields.Many2one("commission.period", required=True, ondelete="cascade", index=True)
    manager_id = fields.Many2one(
        "commission.seller",
        required=True,
        domain="[('role', 'in', ['manager', 'hybrid'])]",
        ondelete="cascade",
    )
    location_id = fields.Many2one(
        "commission.location",
        string="Localidad",
        help="Opcional. Si se informa, la regla solo aplica a ventas del equipo en esa localidad.",
    )
    min_seller_sales = fields.Float(
        string="Venta mínima por vendedor",
        required=True,
        default=0.0,
        digits=(16, 4),
    )
    commission_percent = fields.Float(string="Comisión gestión (%)", required=True, digits=(16, 4))
    basis = fields.Selection(
        [("net", "Total neto"), ("price", "Total precio"), ("margin", "Utilidad")],
        default="net",
        required=True,
    )
    require_location_target = fields.Boolean(default=True, string="Exigir meta de local")


    @api.constrains("period_id", "manager_id", "location_id")
    def _check_unique_manager_rule(self):
        for rec in self:
            domain = [("id", "!=", rec.id), ("period_id", "=", rec.period_id.id), ("manager_id", "=", rec.manager_id.id)]
            domain.append(("location_id", "=", rec.location_id.id if rec.location_id else False))
            if self.search_count(domain):
                raise ValidationError("Ya existe una regla para ese administrador, período y localidad.")

    @api.constrains("min_seller_sales", "commission_percent")
    def _check_values(self):
        for rec in self:
            if rec.min_seller_sales < 0 or rec.commission_percent < 0:
                raise ValidationError("Los valores de la regla no pueden ser negativos.")


class CommissionProjectRule(models.Model):
    _name = "commission.project.rule"
    _description = "Regla de comisión por origen para proyectos"
    _order = "period_id, seller_id, origin"

    period_id = fields.Many2one(
        "commission.period",
        string="Período",
        ondelete="cascade",
        help="Si se informa, la regla solo aplica a ese período. Si queda vacío, actúa como regla general.",
    )
    seller_id = fields.Many2one("commission.seller", required=True, ondelete="cascade", index=True)
    origin = fields.Char(required=True, index=True)
    commission_percent = fields.Float(string="Comisión (%)", required=True, digits=(16, 4))
    basis = fields.Selection(
        [("net", "Total neto"), ("price", "Total precio"), ("margin", "Utilidad")],
        default="net",
        required=True,
    )
    active = fields.Boolean(default=True)


    @api.constrains("period_id", "seller_id", "origin")
    def _check_unique_project_rule(self):
        for rec in self:
            domain = [("id", "!=", rec.id), ("seller_id", "=", rec.seller_id.id), ("origin", "=", rec.origin)]
            domain.append(("period_id", "=", rec.period_id.id if rec.period_id else False))
            if self.search_count(domain):
                raise ValidationError("Ya existe una regla para ese vendedor, origen y período.")

    @api.constrains("commission_percent")
    def _check_percent(self):
        for rec in self:
            if rec.commission_percent < 0:
                raise ValidationError("El porcentaje no puede ser negativo.")


class CommissionLiquidationRule(models.Model):
    _name = "commission.liquidation.rule"
    _description = "Bono por productos en liquidación"
    _order = "period_id, seller_id"

    period_id = fields.Many2one("commission.period", required=True, ondelete="cascade", index=True)
    seller_id = fields.Many2one(
        "commission.seller",
        string="Vendedor",
        ondelete="cascade",
        help="Vacío = regla general para todos los vendedores del período.",
    )
    location_id = fields.Many2one(
        "commission.location",
        string="Localidad",
        help="Opcional. Restringe el bono a una localidad.",
    )
    indicator_value = fields.Float(
        string="Valor Indica_Precio",
        default=3.0,
        required=True,
        help="La venta de liquidación se identifica por este valor. Por defecto 3.",
    )
    min_sales_amount = fields.Float(
        string="Monto mínimo de ventas",
        required=True,
        default=0.0,
        digits=(16, 4),
    )
    amount_per_m2 = fields.Float(
        string="Valor por m²",
        required=True,
        digits=(16, 4),
    )
    basis = fields.Selection(
        [("net", "Total neto"), ("price", "Total precio")],
        default="net",
        required=True,
        string="Base para validar monto mínimo",
    )

    @api.constrains("period_id", "seller_id", "location_id")
    def _check_unique_liquidation_rule(self):
        for rec in self:
            domain = [("id", "!=", rec.id), ("period_id", "=", rec.period_id.id)]
            domain.append(("seller_id", "=", rec.seller_id.id if rec.seller_id else False))
            domain.append(("location_id", "=", rec.location_id.id if rec.location_id else False))
            if self.search_count(domain):
                raise ValidationError("Ya existe una regla de liquidación para ese período, vendedor y localidad.")


class CommissionDocumentType(models.Model):
    _name = "commission.document.type"
    _description = "Tipo de documento y signo para comisiones"
    _order = "code"

    code = fields.Char(required=True, index=True)
    name = fields.Char(required=True)
    sign = fields.Selection([("1", "+1 Venta"), ("-1", "-1 Devolución / NC")], default="1", required=True)
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ("document_type_code_unique", "unique(code)", "El tipo de documento debe ser único."),
    ]
