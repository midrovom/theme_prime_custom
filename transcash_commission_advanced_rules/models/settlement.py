from collections import defaultdict

from odoo import _, models
from odoo.exceptions import UserError


class CommissionSettlement(models.Model):
    _inherit = "commission.settlement"

    def _advanced_liquidation_rules_for_seller(self, seller):
        """Return the effective liquidation rules using the parent's precedence.

        A seller-specific rule replaces a generic rule for the same location.  The
        helper intentionally returns recordsets only; product matching stays in the
        parent method `_promotion_lines_for_rule`, so the uploaded promotion list by
        normalized product name continues to be the single source of truth.
        """
        self.ensure_one()
        rules = self.period_id.liquidation_rule_ids.filtered(
            lambda rule: not rule.seller_id or rule.seller_id == seller
        )
        best_by_location = {}
        for rule in rules.sorted(key=lambda item: (bool(item.seller_id), item.id)):
            best_by_location[rule.location_id.id or 0] = rule
        return self.env["commission.liquidation.rule"].browse(
            [rule.id for rule in best_by_location.values()]
        )

    def _apply_liquidation_commission_penalty(
        self,
        result,
        seller,
        seller_sales,
        Detail,
        promotion_names=None,
    ):
        """Implement the three-state liquidation rule.

        1. Below the protected minimum: use the existing penalty engine.
        2. From protected minimum up to the full target: no penalty, no m² bonus.
        3. At/above the full target: no penalty; the existing bonus method pays m².

        The m² bonus routine itself is not replaced.  Therefore state 2 naturally
        receives no bonus because the original full target has not been reached.
        """
        self.ensure_one()
        rules = self._advanced_liquidation_rules_for_seller(seller)
        if not rules:
            return super()._apply_liquidation_commission_penalty(
                result,
                seller,
                seller_sales,
                Detail,
                promotion_names=promotion_names,
            )

        failed_full_target = []
        failed_protected_minimum = []
        middle_state = []

        for rule in rules:
            lines = self._promotion_lines_for_rule(
                seller_sales,
                rule,
                promotion_names=promotion_names,
            )
            # Respect the configured basis of each liquidation rule.  This is the
            # same semantic used by the parent commission engine and avoids assuming
            # Total Neto when a different basis was selected.
            sales_amount = sum(line.amount_for_basis(rule.basis) for line in lines)
            full_target = rule.min_sales_amount or 0.0
            protected_minimum = rule.effective_penalty_free_minimum

            if sales_amount < full_target:
                failed_full_target.append((rule, sales_amount))
            if sales_amount < protected_minimum:
                failed_protected_minimum.append((rule, sales_amount))
            elif sales_amount < full_target:
                middle_state.append(
                    (rule, sales_amount, protected_minimum, full_target)
                )

        # Any applicable rule below the protected minimum means that the original
        # penalty behavior applies.  This also preserves the existing seller-level
        # exemption and the configured reduction in percentage points.
        if failed_protected_minimum:
            return super()._apply_liquidation_commission_penalty(
                result,
                seller,
                seller_sales,
                Detail,
                promotion_names=promotion_names,
            )

        # All full targets met: delegate to the original method, which leaves the
        # commission unpenalized.  The original bonus method separately pays m².
        if not failed_full_target:
            return super()._apply_liquidation_commission_penalty(
                result,
                seller,
                seller_sales,
                Detail,
                promotion_names=promotion_names,
            )

        # Only intermediate states remain.  Explicitly reset the penalty audit
        # fields because settlements can be recalculated on the same result record.
        result.write(
            {
                "liquidation_penalty_applied": False,
                "liquidation_penalty": 0.0,
                "liquidation_penalty_percent": 0.0,
                "liquidation_rate_reduction": 0.0,
                "liquidation_penalty_base": 0.0,
                "liquidation_rate_adjusted": False,
            }
        )

        descriptions = []
        for rule, sales_amount, protected_minimum, full_target in middle_state:
            location = (
                rule.location_id.display_name if rule.location_id else _("Todas")
            )
            descriptions.append(
                _(
                    "%(location)s: venta promocional %(sales).2f; mínimo sin "
                    "castigo %(minimum).2f; meta para bono %(target).2f. "
                    "No hay castigo y todavía no corresponde bono por m²."
                )
                % {
                    "location": location,
                    "sales": sales_amount,
                    "minimum": protected_minimum,
                    "target": full_target,
                }
            )

        if descriptions:
            Detail.create(
                {
                    "result_id": result.id,
                    "detail_type": "liquidation_penalty",
                    "description": "\n".join(descriptions),
                    "basis_amount": 0.0,
                    "rate": 0.0,
                    "amount": 0.0,
                    "eligible": True,
                }
            )
        return True

    def _calculate_manager_commission(
        self,
        result,
        manager,
        commissionable_by_seller,
        qualification_by_seller,
        location_target_status,
        Detail,
        target_by_seller=None,
    ):
        """Replace the single manager rate with the last sales tier reached.

        The parent calculation runs first so all of its business conditions remain in
        force, especially the assigned-local target.  For rules with advanced tiers,
        only the rate and resulting amount are replaced by the applicable tier.
        """
        parent_result = super()._calculate_manager_commission(
            result,
            manager,
            commissionable_by_seller,
            qualification_by_seller,
            location_target_status,
            Detail,
            target_by_seller=target_by_seller,
        )

        self.ensure_one()
        tier_rules = self.period_id.manager_seller_rule_ids.filtered(
            lambda rule: (
                rule.active
                and rule.manager_id == manager
                and rule.management_id
                and rule.management_id.active
                and rule.management_tier_ids
            )
        )
        if not tier_rules:
            return parent_result

        rules_by_seller = {rule.seller_id.id: rule for rule in tier_rules}
        empty_sales = self.env["commission.sale"].browse()
        management_details = result.detail_ids.filtered(
            lambda detail: detail.detail_type == "management"
            and detail.managed_seller_id
        )

        for detail in management_details:
            rule = rules_by_seller.get(detail.managed_seller_id.id)
            if not rule:
                continue

            qualification_lines = qualification_by_seller.get(
                rule.seller_id.id, empty_sales
            )
            commissionable_lines = commissionable_by_seller.get(
                rule.seller_id.id, empty_sales
            )
            qualification_amount = sum(
                line.amount_for_basis(rule.basis) for line in qualification_lines
            )
            basis_amount = sum(
                line.amount_for_basis(rule.basis) for line in commissionable_lines
            )
            tier = rule._get_applicable_management_tier(qualification_amount)

            # The first active tier is mirrored into the parent's legacy minimum.
            # Therefore, when a tier is reached but the parent says "not eligible",
            # another parent condition (principally the local target) failed and must
            # remain failed.
            parent_conditions_ok = bool(detail.eligible)
            eligible = bool(tier) and parent_conditions_ok
            rate = tier.commission_percent if tier else 0.0
            amount = basis_amount * rate / 100.0 if eligible else 0.0

            tier_text = (
                _("rango %(threshold).2f → %(rate).4f%%")
                % {
                    "threshold": tier.sales_threshold,
                    "rate": tier.commission_percent,
                }
                if tier
                else _("sin rango alcanzado")
            )
            previous_description = detail.description or ""
            detail.write(
                {
                    "qualification_amount": qualification_amount,
                    "basis_amount": basis_amount,
                    "rate": rate,
                    "amount": amount,
                    "eligible": eligible,
                    "description": (
                        "%s | %s" % (previous_description, tier_text)
                        if previous_description
                        else tier_text
                    ),
                }
            )

        result.management_commission = sum(
            result.detail_ids.filtered(
                lambda detail: detail.detail_type == "management"
            ).mapped("amount")
        )
        return parent_result

    def _calculate_project_commission(
        self,
        result,
        seller,
        seller_sales,
        Detail,
        qualification_sales=None,
        target=None,
        rules=None,
    ):
        """Project rate = reached global tier factor × each origin's base rate.

        The factor is *stepwise*, never proportional/interpolated.  Example:
        global tier 8,000 -> 0.80 and 10,000 -> 1.00.  At 8,500 the factor remains
        0.80.  An origin configured at 2.00% therefore pays 1.60%.
        """
        self.ensure_one()
        if seller.is_corporate_project or seller.role not in ("project", "hybrid"):
            return

        if qualification_sales is None:
            qualification_sales = seller_sales

        if rules is None:
            rules = self.env["commission.project.rule"].search(
                [
                    ("seller_id", "=", seller.id),
                    ("active", "=", True),
                    "|",
                    ("period_id", "=", False),
                    ("period_id", "=", self.period_id.id),
                ]
            )
        if not rules:
            return

        # A rule tied to this period replaces a generic rule for the same origin.
        best_rule_by_origin = {}
        for rule in rules.sorted(key=lambda item: (bool(item.period_id), item.id)):
            origin_key = (rule.origin or "").strip().casefold()
            if origin_key:
                best_rule_by_origin[origin_key] = rule

        sales_ids_by_origin = defaultdict(list)
        qualification_ids_by_origin = defaultdict(list)
        for line in seller_sales:
            sales_ids_by_origin[(line.origin or "").strip().casefold()].append(line.id)
        for line in qualification_sales:
            qualification_ids_by_origin[
                (line.origin or "").strip().casefold()
            ].append(line.id)

        global_rules = [
            rule
            for rule in best_rule_by_origin.values()
            if (rule.rate_mode or "global_tier") == "global_tier"
        ]
        global_qualification_amount = 0.0
        global_tier = self.env["commission.seller.target.tier"]
        tier_factor = 0.0

        if global_rules:
            if not target:
                raise UserError(
                    _(
                        "El vendedor de proyectos %(seller)s usa comisión por factor "
                        "de rango global, pero no tiene una meta/rangos configurados "
                        "en el período."
                    )
                    % {"seller": seller.display_name}
                )
            global_qualification_amount = sum(
                line.amount_for_basis(target.basis) for line in qualification_sales
            )
            global_tier = target._get_applicable_sales_tier(
                global_qualification_amount
            )
            tier_factor = global_tier.commission_percent if global_tier else 0.0

        for origin_key, rule in best_rule_by_origin.items():
            origin_lines = self.env["commission.sale"].browse(
                sales_ids_by_origin.get(origin_key, [])
            )
            qualification_origin_lines = self.env["commission.sale"].browse(
                qualification_ids_by_origin.get(origin_key, [])
            )
            if not origin_lines and not qualification_origin_lines:
                continue

            basis_amount = sum(
                line.amount_for_basis(rule.basis) for line in origin_lines
            )
            qualification_amount = sum(
                line.amount_for_basis(rule.basis)
                for line in qualification_origin_lines
            )
            mode = rule.rate_mode or "global_tier"

            if mode == "fixed":
                effective_rate = rule.commission_percent
                eligible = effective_rate > 0 and basis_amount != 0
                amount = basis_amount * effective_rate / 100.0 if eligible else 0.0
                description = _(
                    "Proyecto %(origin)s: tasa fija del origen %(rate).4f%%."
                ) % {
                    "origin": rule.origin,
                    "rate": effective_rate,
                }
            else:
                if rule.commission_percent <= 0 and (
                    origin_lines or qualification_origin_lines
                ):
                    raise UserError(
                        _(
                            "El vendedor %(seller)s tiene ventas de proyecto en el "
                            "origen %(origin)s, pero el %% base del origen está en 0."
                        )
                        % {
                            "seller": seller.display_name,
                            "origin": rule.origin,
                        }
                    )

                effective_rate = (
                    rule.commission_percent * tier_factor if global_tier else 0.0
                )
                eligible = bool(global_tier) and effective_rate > 0 and basis_amount != 0
                amount = basis_amount * effective_rate / 100.0 if eligible else 0.0

                if global_tier:
                    description = _(
                        "Proyecto %(origin)s: ventas globales %(global_sales).2f; "
                        "rango desde %(threshold).2f; factor %(factor).4f; "
                        "origen %(origin_rate).4f%%; tasa efectiva %(effective).4f%%."
                    ) % {
                        "origin": rule.origin,
                        "global_sales": global_qualification_amount,
                        "threshold": global_tier.sales_threshold,
                        "factor": tier_factor,
                        "origin_rate": rule.commission_percent,
                        "effective": effective_rate,
                    }
                else:
                    description = _(
                        "Proyecto %(origin)s: ventas globales %(global_sales).2f; "
                        "no alcanzó ningún rango global, comisión 0."
                    ) % {
                        "origin": rule.origin,
                        "global_sales": global_qualification_amount,
                    }

            result.project_sales += basis_amount
            result.project_commission += amount
            Detail.create(
                {
                    "result_id": result.id,
                    "detail_type": "project",
                    "description": description,
                    "basis_amount": basis_amount,
                    "qualification_amount": qualification_amount,
                    "basis_type": rule.basis,
                    "project_origin": rule.origin,
                    "rate": effective_rate,
                    "amount": amount,
                    "eligible": eligible,
                }
            )
