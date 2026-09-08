from collections import defaultdict

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class CommissionSettlement(models.Model):
    _name = "commission.settlement"
    _description = "Liquidación de comisiones"
    _order = "id desc"

    name = fields.Char(default=lambda self: _("Nuevo"), required=True, readonly=True, copy=False)
    period_id = fields.Many2one("commission.period", required=True, ondelete="cascade", index=True)
    state = fields.Selection(
        [("draft", "Borrador"), ("calculated", "Calculado"), ("approved", "Aprobado"), ("paid", "Pagado")],
        default="draft",
        required=True,
        index=True,
    )
    calculated_at = fields.Datetime(readonly=True)
    result_ids = fields.One2many("commission.result", "settlement_id", string="Resultados")
    sales_count = fields.Integer(compute="_compute_totals", store=True)
    total_sales = fields.Float(compute="_compute_totals", store=True, digits=(16, 4))
    total_commission = fields.Float(compute="_compute_totals", store=True, digits=(16, 4))

    _sql_constraints = [
        ("period_unique", "unique(period_id)", "Solo puede existir una liquidación por período."),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", _("Nuevo")) == _("Nuevo"):
                vals["name"] = self.env["ir.sequence"].next_by_code("commission.settlement") or _("Nuevo")
        return super().create(vals_list)

    @api.depends("result_ids.total_sales", "result_ids.total_commission", "result_ids.sale_line_count")
    def _compute_totals(self):
        for rec in self:
            rec.total_sales = sum(rec.result_ids.mapped("total_sales"))
            rec.total_commission = sum(rec.result_ids.mapped("total_commission"))
            rec.sales_count = sum(rec.result_ids.mapped("sale_line_count"))

    @api.model
    def create_or_recalculate(self, period):
        settlement = self.search([("period_id", "=", period.id)], limit=1)
        if settlement and settlement.state in ("approved", "paid"):
            raise UserError(_("La liquidación ya está aprobada o pagada."))
        if not settlement:
            settlement = self.create({"period_id": period.id})
        settlement.result_ids.unlink()
        settlement._calculate_results()
        settlement.write({"state": "calculated", "calculated_at": fields.Datetime.now()})
        return settlement

    def _sale_domain(self):
        self.ensure_one()
        return [
            ("registration_date", ">=", self.period_id.date_start),
            ("registration_date", "<=", self.period_id.date_end),
            ("excluded", "=", False),
            ("seller_id", "!=", False),
        ]

    def _calculate_results(self):
        self.ensure_one()
        period = self.period_id
        Sale = self.env["commission.sale"]
        Result = self.env["commission.result"]
        Detail = self.env["commission.result.detail"]

        sales = Sale.search(self._sale_domain())
        by_seller = defaultdict(lambda: Sale.browse())
        for sale in sales:
            by_seller[sale.seller_id.id] |= sale

        # Local sales are calculated once and reused by manager rules.
        location_sales = defaultdict(lambda: Sale.browse())
        for sale in sales:
            if sale.location_id:
                location_sales[sale.location_id.id] |= sale

        location_target_status = {}
        for lt in period.location_target_ids:
            local_lines = location_sales[lt.location_id.id]
            amount = sum(local_lines.mapped(lambda l: l.amount_for_basis(lt.basis)))
            achievement = (amount / lt.target_amount * 100.0) if lt.target_amount else 0.0
            location_target_status[lt.location_id.id] = {
                "sales": amount,
                "target": lt.target_amount,
                "achievement": achievement,
                "required": lt.required_achievement,
                "met": achievement >= lt.required_achievement,
            }

        sellers = self.env["commission.seller"].browse(list(by_seller.keys()))
        # Also include managers with teams/rules even if they had no own sales.
        manager_ids = period.manager_rule_ids.mapped("manager_id").ids
        sellers |= self.env["commission.seller"].browse(manager_ids)

        for seller in sellers:
            seller_sales = by_seller[seller.id]
            result = Result.create({
                "settlement_id": self.id,
                "seller_id": seller.id,
                "sale_line_count": len(seller_sales),
                "total_sales": sum(l.amount_for_basis("net") for l in seller_sales),
            })

            self._calculate_standard_commission(result, seller, seller_sales, Detail)
            self._calculate_project_commission(result, seller, seller_sales, Detail)
            self._calculate_liquidation_bonus(result, seller, seller_sales, Detail)
            self._calculate_manager_commission(result, seller, by_seller, location_target_status, Detail)
            result._recompute_total()

    def _calculate_standard_commission(self, result, seller, seller_sales, Detail):
        period = self.period_id
        targets = period.target_ids.filtered(lambda t: t.seller_id == seller and t.active)
        if seller.role == "project" and not targets:
            return
        for target in targets:
            lines = seller_sales.filtered(lambda l: not target.location_id or l.location_id == target.location_id)
            basis_amount = sum(l.amount_for_basis(target.basis) for l in lines)
            achievement = (basis_amount / target.target_amount * 100.0) if target.target_amount else 0.0
            tiers = target.tier_ids.sorted(lambda t: t.min_achievement)
            eligible = tiers.filtered(
                lambda t: achievement >= t.min_achievement and (not t.max_achievement or achievement <= t.max_achievement)
            )
            tier = eligible[-1] if eligible else self.env["commission.seller.target.tier"]
            rate = tier.commission_percent if tier else 0.0
            commission = basis_amount * rate / 100.0
            result.standard_sales += basis_amount
            result.target_amount += target.target_amount
            result.standard_commission += commission
            if target.target_amount:
                result.achievement_percent = (result.standard_sales / result.target_amount * 100.0)
            Detail.create({
                "result_id": result.id,
                "detail_type": "standard",
                "description": _("Meta %(target).2f - cumplimiento %(achievement).2f%%") % {
                    "target": target.target_amount,
                    "achievement": achievement,
                },
                "location_id": target.location_id.id or False,
                "basis_amount": basis_amount,
                "rate": rate,
                "amount": commission,
            })

    def _calculate_project_commission(self, result, seller, seller_sales, Detail):
        if seller.role not in ("project", "hybrid"):
            return
        rules = self.env["commission.project.rule"].search([
            ("seller_id", "=", seller.id),
            ("active", "=", True),
            "|", ("period_id", "=", self.period_id.id), ("period_id", "=", False),
        ])
        # Period-specific rule wins over generic rule for same origin.
        best_rule = {}
        for rule in rules.sorted(lambda r: (bool(r.period_id), r.id)):
            best_rule[(rule.origin or "").strip().lower()] = rule
        for origin_key, rule in best_rule.items():
            lines = seller_sales.filtered(lambda l: (l.origin or "").strip().lower() == origin_key)
            if not lines:
                continue
            basis_amount = sum(l.amount_for_basis(rule.basis) for l in lines)
            commission = basis_amount * rule.commission_percent / 100.0
            result.project_sales += basis_amount
            result.project_commission += commission
            Detail.create({
                "result_id": result.id,
                "detail_type": "project",
                "description": _("Proyecto / origen: %s") % rule.origin,
                "basis_amount": basis_amount,
                "rate": rule.commission_percent,
                "amount": commission,
            })

    def _calculate_liquidation_bonus(self, result, seller, seller_sales, Detail):
        period = self.period_id
        rules = period.liquidation_rule_ids.filtered(lambda r: not r.seller_id or r.seller_id == seller)
        # Specific seller rule wins over generic rule per location.
        best_by_location = {}
        for rule in rules.sorted(lambda r: (bool(r.seller_id), r.id)):
            key = rule.location_id.id or 0
            best_by_location[key] = rule
        for rule in best_by_location.values():
            lines = seller_sales.filtered(
                lambda l: abs((l.price_indicator or 0.0) - rule.indicator_value) < 0.000001
                and (not rule.location_id or l.location_id == rule.location_id)
            )
            sales_amount = sum(l.amount_for_basis(rule.basis) for l in lines)
            m2 = sum((l.quantity or 0.0) * (l.document_sign or 1.0) for l in lines)
            eligible = sales_amount >= rule.min_sales_amount
            bonus = max(m2, 0.0) * rule.amount_per_m2 if eligible else 0.0
            result.liquidation_sales += sales_amount
            result.liquidation_m2 += m2
            result.liquidation_bonus += bonus
            Detail.create({
                "result_id": result.id,
                "detail_type": "liquidation",
                "description": _("Liquidación: mínimo %(minimum).2f; ventas %(sales).2f; m² %(m2).2f") % {
                    "minimum": rule.min_sales_amount,
                    "sales": sales_amount,
                    "m2": m2,
                },
                "location_id": rule.location_id.id or False,
                "basis_amount": sales_amount,
                "quantity": m2,
                "rate": rule.amount_per_m2,
                "amount": bonus,
                "eligible": eligible,
            })

    def _calculate_manager_commission(self, result, manager, by_seller, location_target_status, Detail):
        if manager.role not in ("manager", "hybrid"):
            return
        rules = self.period_id.manager_rule_ids.filtered(lambda r: r.manager_id == manager)
        team = self.env["commission.seller"].search([("manager_id", "=", manager.id), ("active", "=", True)])
        for rule in rules:
            for seller in team:
                lines = by_seller[seller.id].filtered(lambda l: not rule.location_id or l.location_id == rule.location_id)
                if not lines:
                    continue
                basis_amount = sum(l.amount_for_basis(rule.basis) for l in lines)
                min_ok = basis_amount >= rule.min_seller_sales
                location_ok = True
                achievement = 0.0
                if rule.require_location_target:
                    if rule.location_id:
                        status = location_target_status.get(rule.location_id.id)
                        location_ok = bool(status and status["met"])
                        achievement = status["achievement"] if status else 0.0
                    else:
                        # For a rule without explicit location, every location represented by this seller must meet its configured local target.
                        seller_location_ids = lines.mapped("location_id").ids
                        statuses = [location_target_status.get(loc_id) for loc_id in seller_location_ids]
                        location_ok = bool(statuses) and all(status and status["met"] for status in statuses)
                        achievement = min([s["achievement"] for s in statuses if s] or [0.0])
                eligible = min_ok and location_ok
                commission = basis_amount * rule.commission_percent / 100.0 if eligible else 0.0
                result.management_sales += basis_amount
                result.management_commission += commission
                Detail.create({
                    "result_id": result.id,
                    "detail_type": "management",
                    "description": _("Gestión de %(seller)s | venta mínima %(minimum).2f | cumplimiento local %(achievement).2f%%") % {
                        "seller": seller.name,
                        "minimum": rule.min_seller_sales,
                        "achievement": achievement,
                    },
                    "managed_seller_id": seller.id,
                    "location_id": rule.location_id.id or False,
                    "basis_amount": basis_amount,
                    "rate": rule.commission_percent,
                    "amount": commission,
                    "eligible": eligible,
                })


class CommissionResult(models.Model):
    _name = "commission.result"
    _description = "Resultado por vendedor"
    _order = "total_commission desc, seller_id"

    settlement_id = fields.Many2one("commission.settlement", required=True, ondelete="cascade", index=True)
    seller_id = fields.Many2one("commission.seller", required=True, ondelete="restrict", index=True)
    role = fields.Selection(related="seller_id.role", store=True)
    sale_line_count = fields.Integer(string="Líneas")
    total_sales = fields.Float(string="Ventas netas", digits=(16, 4))

    target_amount = fields.Float(string="Meta", digits=(16, 4))
    standard_sales = fields.Float(string="Ventas meta", digits=(16, 4))
    achievement_percent = fields.Float(string="Cumplimiento %", digits=(16, 4))
    standard_commission = fields.Float(string="Comisión propia", digits=(16, 4))

    project_sales = fields.Float(string="Ventas proyecto", digits=(16, 4))
    project_commission = fields.Float(string="Comisión proyecto", digits=(16, 4))

    management_sales = fields.Float(string="Ventas gestionadas", digits=(16, 4))
    management_commission = fields.Float(string="Comisión gestión", digits=(16, 4))

    liquidation_sales = fields.Float(string="Ventas liquidación", digits=(16, 4))
    liquidation_m2 = fields.Float(string="m² liquidación", digits=(16, 4))
    liquidation_bonus = fields.Float(string="Bono liquidación", digits=(16, 4))

    total_commission = fields.Float(string="Total comisión", digits=(16, 4))
    detail_ids = fields.One2many("commission.result.detail", "result_id", string="Detalle")

    def _recompute_total(self):
        for rec in self:
            rec.total_commission = (
                rec.standard_commission
                + rec.project_commission
                + rec.management_commission
                + rec.liquidation_bonus
            )


class CommissionResultDetail(models.Model):
    _name = "commission.result.detail"
    _description = "Detalle de cálculo de comisión"
    _order = "result_id, detail_type, id"

    result_id = fields.Many2one("commission.result", required=True, ondelete="cascade", index=True)
    detail_type = fields.Selection(
        [
            ("standard", "Comisión por meta"),
            ("project", "Proyecto por origen"),
            ("management", "Gestión de administrador"),
            ("liquidation", "Bono liquidación"),
        ],
        required=True,
        index=True,
    )
    description = fields.Char(required=True)
    managed_seller_id = fields.Many2one("commission.seller", string="Vendedor gestionado")
    location_id = fields.Many2one("commission.location", string="Localidad")
    basis_amount = fields.Float(string="Base", digits=(16, 4))
    quantity = fields.Float(string="Cantidad / m²", digits=(16, 4))
    rate = fields.Float(string="% / tarifa", digits=(16, 4))
    amount = fields.Float(string="Comisión", digits=(16, 4))
    eligible = fields.Boolean(string="Cumple", default=True)
