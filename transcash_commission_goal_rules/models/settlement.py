from collections import defaultdict

from odoo import models, _, api
from odoo.exceptions import UserError


class CommissionSettlement(models.Model):
    _inherit = "commission.settlement"

    def _calculate_results(self):
        """Genera resultados únicamente para vendedores con meta activa."""
        self.ensure_one()
        period = self.period_id
        Sale = self.env["commission.sale"]
        Result = self.env["commission.result"]
        Detail = self.env["commission.result.detail"]

        sales = Sale.search(self._sale_domain())
        by_seller = defaultdict(lambda: Sale.browse())
        location_sales = defaultdict(lambda: Sale.browse())
        for sale in sales:
            by_seller[sale.seller_id.id] |= sale
            if sale.location_id:
                location_sales[sale.location_id.id] |= sale

        location_target_status = {}
        for lt in period.location_target_ids:
            local_lines = location_sales[lt.location_id.id]
            amount = sum(line.amount_for_basis(lt.basis) for line in local_lines)
            achievement = (amount / lt.target_amount * 100.0) if lt.target_amount else 0.0
            location_target_status[lt.location_id.id] = {
                "sales": amount,
                "target": lt.target_amount,
                "achievement": achievement,
                "required": lt.required_achievement,
                "met": achievement >= lt.required_achievement,
            }

        active_targets = period.target_ids.filtered("active")
        target_count = defaultdict(int)
        for target in active_targets:
            target_count[target.seller_id.id] += 1
        duplicated = [seller_id for seller_id, count in target_count.items() if count > 1]
        if duplicated:
            names = ", ".join(self.env["commission.seller"].browse(duplicated).mapped("name"))
            raise UserError(_(
                "Debe existir una sola meta activa por vendedor y período. Revise: %s"
            ) % names)

        # Requisito funcional: vendedores sin meta activa no aparecen en la
        # liquidación, aunque tengan ventas sincronizadas.
        sellers = active_targets.mapped("seller_id")

        for seller in sellers:
            seller_sales = by_seller[seller.id]
            result = Result.create({
                "settlement_id": self.id,
                "seller_id": seller.id,
                "sale_line_count": len(seller_sales),
                "total_sales": sum(line.amount_for_basis("net") for line in seller_sales),
            })

            self._calculate_standard_commission(result, seller, seller_sales, Detail)
            self._calculate_project_commission(result, seller, seller_sales, Detail)
            self._calculate_liquidation_bonus(result, seller, seller_sales, Detail)
            self._calculate_manager_commission(
                result, seller, by_seller, location_target_status, Detail
            )
            result._recompute_total()

    def _calculate_standard_commission(self, result, seller, seller_sales, Detail):
        """La meta/comisión propia del vendedor no depende de localidad."""
        targets = self.period_id.target_ids.filtered(
            lambda target: target.seller_id == seller and target.active
        )
        if not targets:
            return
        if len(targets) > 1:
            raise UserError(_(
                "El vendedor %s tiene más de una meta activa en el período."
            ) % seller.display_name)

        target = targets[0]
        basis_amount = sum(line.amount_for_basis(target.basis) for line in seller_sales)
        achievement = (
            basis_amount / target.target_amount * 100.0
            if target.target_amount
            else 0.0
        )
        tiers = target.tier_ids.sorted(lambda tier: tier.min_achievement)
        eligible_tiers = tiers.filtered(
            lambda tier: achievement >= tier.min_achievement
            and (not tier.max_achievement or achievement <= tier.max_achievement)
        )
        tier = (
            eligible_tiers[-1]
            if eligible_tiers
            else self.env["commission.seller.target.tier"]
        )
        rate = tier.commission_percent if tier else 0.0
        commission = basis_amount * rate / 100.0

        result.standard_sales = basis_amount
        result.target_amount = target.target_amount
        result.achievement_percent = achievement
        result.standard_commission = commission

        Detail.create({
            "result_id": result.id,
            "detail_type": "standard",
            "description": _(
                "Meta %(target).2f - cumplimiento %(achievement).2f%% - todas las localidades"
            ) % {
                "target": target.target_amount,
                "achievement": achievement,
            },
            "basis_amount": basis_amount,
            "rate": rate,
            "amount": commission,
            "eligible": bool(tier),
        })

    def _calculate_manager_commission(
        self, result, manager, by_seller, location_target_status, Detail
    ):
        """Calcula gestión con umbral independiente por vendedor.

        Condiciones para pagar al administrador por cada vendedor a cargo:
        1) El vendedor alcanza el mínimo administrativo configurado para él.
           Puede ser un monto fijo o un porcentaje de su meta propia.
        2) El local asignado a la regla cumple su meta local.
        3) La comisión se paga con el porcentaje específico de esa regla.

        La meta propia del vendedor NO decide directamente la elegibilidad del
        administrador, salvo cuando se selecciona expresamente el modo
        "% de la meta" para calcular el umbral administrativo.
        """
        if manager.role not in ("manager", "hybrid"):
            return

        rules = self.period_id.manager_seller_rule_ids.filtered(
            lambda rule: (
                rule.manager_id == manager
                and rule.active
                and rule.management_id
                and rule.management_id.active
            )
        )
        Target = self.env["commission.seller.target"]

        for rule in rules:
            # Todas las ventas del vendedor cuentan para su mínimo y para la base
            # de gestión. El local de la regla solo valida el cumplimiento local.
            lines = by_seller[rule.seller_id.id]
            basis_amount = sum(line.amount_for_basis(rule.basis) for line in lines)

            target = Target.search([
                ("period_id", "=", self.period_id.id),
                ("seller_id", "=", rule.seller_id.id),
                ("active", "=", True),
            ], limit=1)

            minimum_available = True
            if rule.minimum_type == "target_percent":
                minimum_available = bool(target)
                effective_minimum = (
                    target.target_amount * rule.minimum_target_percent / 100.0
                    if target
                    else 0.0
                )
                minimum_label = _("%(percent).2f%% de meta") % {
                    "percent": rule.minimum_target_percent,
                }
            else:
                effective_minimum = rule.minimum_amount
                minimum_label = _("monto fijo")

            minimum_ok = minimum_available and basis_amount >= effective_minimum

            status = location_target_status.get(rule.location_id.id)
            location_ok = bool(status and status["met"])
            location_achievement = status["achievement"] if status else 0.0

            eligible = minimum_ok and location_ok
            commission = (
                basis_amount * rule.commission_percent / 100.0
                if eligible
                else 0.0
            )

            result.management_sales += basis_amount
            result.management_commission += commission

            target_reference = target.target_amount if target else 0.0
            Detail.create({
                "result_id": result.id,
                "detail_type": "management",
                "description": _(
                    "Gestión %(seller)s | mínimo admin %(minimum).2f (%(mode)s) | "
                    "meta vendedor %(target).2f | local %(location)s %(achievement).2f%%"
                ) % {
                    "seller": rule.seller_id.name,
                    "minimum": effective_minimum,
                    "mode": minimum_label,
                    "target": target_reference,
                    "location": rule.location_id.display_name,
                    "achievement": location_achievement,
                },
                "managed_seller_id": rule.seller_id.id,
                "location_id": rule.location_id.id,
                "basis_amount": basis_amount,
                "rate": rule.commission_percent,
                "amount": commission,
                "eligible": eligible,
            })

    def action_print_settlement(self):
        self.ensure_one()
        return self.env.ref(
            "transcash_commission_goal_rules.action_report_commission_settlement_total"
        ).report_action(self)


class CommissionResult(models.Model):
    _inherit = "commission.result"

    def action_print_individual(self):
        self.ensure_one()
        return self.env.ref(
            "transcash_commission_goal_rules.action_report_commission_result_individual"
        ).report_action(self)
