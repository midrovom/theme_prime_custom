from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class CommissionLiquidationRule(models.Model):
    _inherit = "commission.liquidation.rule"

    penalty_free_min_sales_amount = fields.Float(
        string="Mínimo para evitar castigo",
        help=(
            "Venta mínima de productos de liquidación/promoción que evita la reducción "
            "de la tasa de comisión, aun cuando todavía no se alcance la meta completa "
            "que habilita el bono por m². Si se deja en 0, se usa la meta completa como "
            "mínimo para evitar el castigo, conservando el comportamiento anterior."
        ),
    )
    effective_penalty_free_minimum = fields.Float(
        string="Mínimo efectivo sin castigo",
        compute="_compute_effective_penalty_free_minimum",
        help="Mínimo realmente utilizado para decidir si se aplica o no el castigo.",
    )

    @api.depends("penalty_free_min_sales_amount", "min_sales_amount")
    def _compute_effective_penalty_free_minimum(self):
        for rule in self:
            rule.effective_penalty_free_minimum = (
                rule.penalty_free_min_sales_amount
                if rule.penalty_free_min_sales_amount > 0
                else rule.min_sales_amount
            )

    @api.constrains("penalty_free_min_sales_amount", "min_sales_amount")
    def _check_penalty_free_minimum(self):
        for rule in self:
            if rule.penalty_free_min_sales_amount < 0:
                raise ValidationError(_("El mínimo para evitar castigo no puede ser negativo."))
            if (
                rule.penalty_free_min_sales_amount > 0
                and rule.min_sales_amount > 0
                and rule.penalty_free_min_sales_amount > rule.min_sales_amount
            ):
                raise ValidationError(
                    _(
                        "El mínimo para evitar castigo (%(minimum).2f) no puede ser mayor "
                        "que la meta completa de liquidación (%(target).2f)."
                    )
                    % {
                        "minimum": rule.penalty_free_min_sales_amount,
                        "target": rule.min_sales_amount,
                    }
                )

    def copy_to_period(self, destination_period):
        self.ensure_one()
        new_rule = super().copy_to_period(destination_period)
        new_rule.penalty_free_min_sales_amount = self.penalty_free_min_sales_amount
        return new_rule


class CommissionManagerSellerRule(models.Model):
    _inherit = "commission.manager.seller.rule"

    management_tier_ids = fields.One2many(
        "commission.manager.seller.tier",
        "seller_rule_id",
        string="Rangos de comisión de gestión",
        copy=True,
    )
    management_tier_count = fields.Integer(
        string="Rangos",
        compute="_compute_management_tier_count",
    )

    @api.depends("management_tier_ids")
    def _compute_management_tier_count(self):
        for record in self:
            record.management_tier_count = len(record.management_tier_ids)

    def _sync_legacy_values_from_management_tiers(self):
        """Keep the existing manager engine compatible with the first tier.

        The parent module checks a minimum and a single percentage before creating the
        management detail.  When ranges are configured we mirror the first range into
        those legacy fields so the parent eligibility logic still reflects the first
        valid threshold.  The final selected percentage is replaced later by the tier
        actually reached.
        """
        for record in self:
            tiers = record.management_tier_ids.filtered("active").sorted(
                key=lambda tier: (tier.sales_threshold, tier.id)
            )
            if not tiers:
                continue
            first = tiers[0]
            values = {}
            if record.minimum_type != "fixed":
                values["minimum_type"] = "fixed"
            if record.minimum_amount != first.sales_threshold:
                values["minimum_amount"] = first.sales_threshold
            if record.commission_percent != first.commission_percent:
                values["commission_percent"] = first.commission_percent
            if values:
                record.with_context(skip_management_tier_sync=True).write(values)

    def _get_applicable_management_tier(self, sales_amount):
        self.ensure_one()
        tiers = self.management_tier_ids.filtered(
            lambda tier: tier.active and tier.sales_threshold <= sales_amount
        ).sorted(key=lambda tier: (tier.sales_threshold, tier.id))
        return tiers[-1:] if tiers else self.env["commission.manager.seller.tier"]


class CommissionManagerSellerTier(models.Model):
    _name = "commission.manager.seller.tier"
    _description = "Rango de comisión de gestión del administrador"
    _order = "sales_threshold, id"

    seller_rule_id = fields.Many2one(
        "commission.manager.seller.rule",
        string="Regla administrador / vendedor",
        required=True,
        ondelete="cascade",
        index=True,
    )
    sales_threshold = fields.Float(
        string="Venta mínima del rango",
        required=True,
        help="Venta mínima del vendedor a cargo para que el administrador alcance este rango.",
    )
    commission_percent = fields.Float(
        string="Comisión administrador (%)",
        required=True,
        help="Porcentaje que gana el administrador sobre la base comisionable del vendedor al alcanzar este rango.",
    )
    active = fields.Boolean(default=True)

    _sql_constraints = [
        (
            "manager_seller_tier_threshold_unique",
            "unique(seller_rule_id, sales_threshold)",
            "No puede repetir el mismo monto de rango para un vendedor dentro de la misma regla de gestión.",
        ),
    ]

    @api.constrains("sales_threshold", "commission_percent")
    def _check_values(self):
        for tier in self:
            if tier.sales_threshold < 0:
                raise ValidationError(_("La venta mínima del rango no puede ser negativa."))
            if tier.commission_percent < 0:
                raise ValidationError(_("El porcentaje de comisión no puede ser negativo."))

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records.mapped("seller_rule_id")._sync_legacy_values_from_management_tiers()
        return records

    def write(self, vals):
        parents = self.mapped("seller_rule_id")
        result = super().write(vals)
        (parents | self.mapped("seller_rule_id"))._sync_legacy_values_from_management_tiers()
        return result

    def unlink(self):
        parents = self.mapped("seller_rule_id")
        result = super().unlink()
        parents.exists()._sync_legacy_values_from_management_tiers()
        return result


class CommissionManagerGoalRule(models.Model):
    _inherit = "commission.manager.goal.rule"

    def copy_to_period(self, destination_period):
        self.ensure_one()
        new_management = super().copy_to_period(destination_period)

        source_by_seller = {
            line.seller_id.id: line
            for line in self.line_ids
            if line.seller_id and line.management_tier_ids
        }
        for new_line in new_management.line_ids:
            source = source_by_seller.get(new_line.seller_id.id)
            if not source:
                continue
            existing_thresholds = set(new_line.management_tier_ids.mapped("sales_threshold"))
            for tier in source.management_tier_ids.sorted(
                key=lambda item: (item.sales_threshold, item.id)
            ):
                if tier.sales_threshold in existing_thresholds:
                    continue
                self.env["commission.manager.seller.tier"].create(
                    {
                        "seller_rule_id": new_line.id,
                        "sales_threshold": tier.sales_threshold,
                        "commission_percent": tier.commission_percent,
                        "active": tier.active,
                    }
                )
                existing_thresholds.add(tier.sales_threshold)
        return new_management


class CommissionProjectRule(models.Model):
    _inherit = "commission.project.rule"

    rate_mode = fields.Selection(
        selection=[
            (
                "global_tier",
                "Factor del rango global × % del origen",
            ),
            (
                "fixed",
                "% fijo por origen (sin factor global)",
            ),
        ],
        string="Forma de calcular tasa",
        default="global_tier",
        required=True,
        help=(
            "En modo Factor del rango global, el vendedor alcanza un rango por sus ventas "
            "globales y el valor de comisión de ese rango se usa como factor. Ejemplo: "
            "factor 0,80 × origen Importado 2,00% = tasa efectiva 1,60%."
        ),
    )
    commission_percent = fields.Float(
        string="% base del origen",
        required=True,
        default=0.0,
        digits=(16, 4),
        help=(
            "Porcentaje propio del origen. En modo global se multiplica por el factor "
            "obtenido del rango de ventas del vendedor; en modo fijo se usa directamente."
        ),
    )
