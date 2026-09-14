from collections import defaultdict

from odoo import fields, models, _, api
from odoo.exceptions import UserError

from .promotion_utils import normalize_product_name


class CommissionSettlement(models.Model):
    _inherit = "commission.settlement"

    def _calculate_results(self):
        """Calcula la liquidación respetando exclusiones de clientes del período.

        Las ventas de un cliente excluido nunca generan comisión. Si la exclusión
        tiene ``count_for_target`` activa, esas ventas sí participan en los
        cumplimientos (rangos del vendedor, metas locales, mínimos de gestión y
        mínimo de promoción), pero se mantienen fuera de la base comisionable.
        """
        self.ensure_one()
        period = self.period_id
        if period.liquidation_rule_ids and not period.promotion_product_ids:
            raise UserError(_(
                "El período tiene reglas de liquidación, pero no tiene productos en promoción cargados. "
                "Cargue el archivo de promociones en la pestaña Bono liquidación antes de calcular."
            ))
        Sale = self.env["commission.sale"]
        Result = self.env["commission.result"]
        Detail = self.env["commission.result.detail"]

        sales = Sale.search(self._sale_domain())
        commissionable_sales, qualification_sales, exclusion_by_sale = (
            period._classify_sales_by_client_exclusion(sales)
        )

        all_by_seller = defaultdict(lambda: Sale.browse())
        commissionable_by_seller = defaultdict(lambda: Sale.browse())
        qualification_by_seller = defaultdict(lambda: Sale.browse())
        qualification_location_sales = defaultdict(lambda: Sale.browse())

        for sale in sales:
            all_by_seller[sale.seller_id.id] |= sale
        for sale in commissionable_sales:
            commissionable_by_seller[sale.seller_id.id] |= sale
        for sale in qualification_sales:
            qualification_by_seller[sale.seller_id.id] |= sale
            if sale.location_id:
                qualification_location_sales[sale.location_id.id] |= sale

        location_target_status = {}
        for lt in period.location_target_ids:
            local_lines = qualification_location_sales[lt.location_id.id]
            amount = sum(line.amount_for_basis(lt.basis) for line in local_lines)
            achievement = (amount / lt.target_amount * 100.0) if lt.target_amount else 0.0
            location_target_status[lt.location_id.id] = {
                "sales": amount,
                "target": lt.target_amount,
                "achievement": achievement,
                "required": lt.required_achievement,
                "met": achievement >= lt.required_achievement,
            }

        active_management_lines = period.manager_seller_rule_ids.filtered(
            lambda rule: rule.active and rule.management_id and rule.management_id.active
        )
        management_count = defaultdict(int)
        for rule in active_management_lines:
            management_count[rule.seller_id.id] += 1
        duplicated_management = [
            seller_id for seller_id, count in management_count.items() if count > 1
        ]
        if duplicated_management:
            names = ", ".join(
                self.env["commission.seller"].browse(duplicated_management).mapped("name")
            )
            raise UserError(_(
                "Hay vendedores asignados más de una vez en la gestión de "
                "administradores para este período. Revise: %s"
            ) % names)

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

        sellers = active_targets.mapped("seller_id")
        period_project_rules = period.project_rule_ids.filtered("active")
        sellers |= period_project_rules.mapped("seller_id")

        global_project_rules = self.env["commission.project.rule"].search([
            ("active", "=", True),
            ("period_id", "=", False),
        ])
        for rule in global_project_rules:
            origin_key = (rule.origin or "").strip().lower()
            has_matching_sales = any(
                (line.origin or "").strip().lower() == origin_key
                for line in commissionable_by_seller[rule.seller_id.id]
            )
            if has_matching_sales:
                sellers |= rule.seller_id

        active_management = period.manager_goal_rule_ids.filtered("active")
        sellers |= active_management.mapped("manager_id")
        sellers |= period.liquidation_rule_ids.filtered(
            lambda rule: bool(rule.seller_id)
        ).mapped("seller_id")
        sellers = sellers.filtered("active")

        for seller in sellers.sorted(lambda s: (s.code or "", s.name or "")):
            seller_all_sales = all_by_seller[seller.id]
            seller_commissionable_sales = commissionable_by_seller[seller.id]
            seller_qualification_sales = qualification_by_seller[seller.id]

            all_net = sum(line.amount_for_basis("net") for line in seller_all_sales)
            commissionable_net = sum(
                line.amount_for_basis("net") for line in seller_commissionable_sales
            )
            qualification_net = sum(
                line.amount_for_basis("net") for line in seller_qualification_sales
            )
            excluded_ids = set(seller_all_sales.ids) - set(seller_commissionable_sales.ids)
            excluded_sales = Sale.browse(list(excluded_ids))

            result = Result.create({
                "settlement_id": self.id,
                "seller_id": seller.id,
                "sale_line_count": len(seller_commissionable_sales),
                "total_sales": commissionable_net,
                "gross_sales_before_client_exclusions": all_net,
                "qualification_sales": qualification_net,
                "excluded_client_sales": sum(
                    line.amount_for_basis("net") for line in excluded_sales
                ),
                "excluded_client_line_count": len(excluded_sales),
            })

            self._calculate_standard_commission(
                result,
                seller,
                seller_commissionable_sales,
                Detail,
                qualification_sales=seller_qualification_sales,
            )
            self._calculate_project_commission(
                result, seller, seller_commissionable_sales, Detail
            )
            self._calculate_liquidation_bonus(
                result,
                seller,
                seller_commissionable_sales,
                Detail,
                qualification_sales=seller_qualification_sales,
            )
            self._calculate_manager_commission(
                result,
                seller,
                commissionable_by_seller,
                qualification_by_seller,
                location_target_status,
                Detail,
            )
            self._apply_liquidation_commission_penalty(
                result, seller, seller_qualification_sales, Detail
            )
            result._recompute_total()

        self._rebuild_dashboard_lines(sales, exclusion_by_sale)

    def _calculate_standard_commission(
        self, result, seller, seller_sales, Detail, qualification_sales=None
    ):
        """Rango por ventas: califica con una base y comisiona con otra.

        ``qualification_sales`` puede incluir ventas de clientes excluidos que el
        período haya marcado para contar en metas. ``seller_sales`` contiene solo
        ventas que sí pueden generar comisión.
        """
        qualification_sales = qualification_sales if qualification_sales is not None else seller_sales
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
        qualification_amount = sum(
            line.amount_for_basis(target.basis) for line in qualification_sales
        )
        commissionable_amount = sum(
            line.amount_for_basis(target.basis) for line in seller_sales
        )
        achievement = (
            qualification_amount / target.target_amount * 100.0
            if target.target_amount
            else 0.0
        )

        tiers = target.tier_ids.sorted(lambda tier: (tier.sales_threshold, tier.id))
        tier = target._get_applicable_sales_tier(qualification_amount)
        eligible = bool(tier)
        rate = tier.commission_percent if tier else 0.0
        commission = commissionable_amount * rate / 100.0
        minimum_required = tiers[0].sales_threshold if tiers else 0.0
        selected_threshold = tier.sales_threshold if tier else 0.0
        description = _(
            "Meta referencial %(target).2f - ventas para rango/meta %(qualifying).2f - "
            "base comisionable %(commissionable).2f - cumplimiento %(achievement).2f%% - "
            "mínimo para comisionar %(minimum).2f - rango aplicado desde %(threshold).2f - "
            "tasa %(rate).4f%%"
        ) % {
            "target": target.target_amount,
            "qualifying": qualification_amount,
            "commissionable": commissionable_amount,
            "achievement": achievement,
            "minimum": minimum_required,
            "threshold": selected_threshold,
            "rate": rate,
        }

        result.standard_sales = qualification_amount
        result.target_amount = target.target_amount
        result.achievement_percent = achievement
        result.standard_commission = commission

        Detail.create({
            "result_id": result.id,
            "detail_type": "standard",
            "description": description,
            "basis_amount": commissionable_amount,
            "qualification_amount": qualification_amount,
            "basis_type": target.basis,
            "rate": rate,
            "amount": commission,
            "eligible": eligible,
        })

    def _calculate_project_commission(self, result, seller, seller_sales, Detail):
        """Proyecto/origen sobre ventas comisionables (clientes excluidos no pagan)."""
        if seller.role not in ("project", "hybrid"):
            return
        rules = self.env["commission.project.rule"].search([
            ("seller_id", "=", seller.id),
            ("active", "=", True),
            "|", ("period_id", "=", self.period_id.id), ("period_id", "=", False),
        ])
        best_rule = {}
        for rule in rules.sorted(lambda rule: (bool(rule.period_id), rule.id)):
            best_rule[(rule.origin or "").strip().lower()] = rule

        for origin_key, rule in best_rule.items():
            lines = seller_sales.filtered(
                lambda line: (line.origin or "").strip().lower() == origin_key
            )
            if not lines:
                continue
            basis_amount = sum(line.amount_for_basis(rule.basis) for line in lines)
            commission = basis_amount * rule.commission_percent / 100.0
            result.project_sales += basis_amount
            result.project_commission += commission
            Detail.create({
                "result_id": result.id,
                "detail_type": "project",
                "description": _("Proyecto / origen: %s") % rule.origin,
                "basis_amount": basis_amount,
                "qualification_amount": basis_amount,
                "basis_type": rule.basis,
                "project_origin": rule.origin,
                "rate": rule.commission_percent,
                "amount": commission,
            })

    def _promotion_name_set(self):
        self.ensure_one()
        return {
            name for name in self.period_id.promotion_product_ids.mapped("normalized_name")
            if name
        }

    def _promotion_lines_for_rule(self, seller_sales, rule):
        """Ventas del vendedor cuyo nombre coincide con el archivo promocional.

        El código de producto y ``Indica_Precio`` se ignoran deliberadamente.
        La comparación es exacta sobre el nombre normalizado (mayúsculas,
        acentos, puntuación y espacios no generan diferencias).
        """
        promotion_names = self._promotion_name_set()
        if not promotion_names:
            return seller_sales.browse([])
        return seller_sales.filtered(
            lambda line: (
                (line.promotion_match_name or normalize_product_name(line.product_name))
                in promotion_names
                and (not rule.location_id or line.location_id == rule.location_id)
            )
        )

    def _calculate_liquidation_bonus(
        self, result, seller, seller_sales, Detail, qualification_sales=None
    ):
        """Bono por promoción: el cliente excluido nunca genera m² comisionados.

        Cuando una exclusión está marcada para contar en metas, sus ventas sí
        ayudan a alcanzar ``min_sales_amount`` pero sus m² y valores quedan fuera
        del bono pagado.
        """
        qualification_sales = qualification_sales if qualification_sales is not None else seller_sales
        period = self.period_id
        rules = period.liquidation_rule_ids.filtered(
            lambda rule: not rule.seller_id or rule.seller_id == seller
        )
        best_by_location = {}
        for rule in rules.sorted(lambda rule: (bool(rule.seller_id), rule.id)):
            best_by_location[rule.location_id.id or 0] = rule

        for rule in best_by_location.values():
            qualifying_lines = self._promotion_lines_for_rule(qualification_sales, rule)
            commissionable_lines = self._promotion_lines_for_rule(seller_sales, rule)
            qualifying_sales_amount = sum(
                line.amount_for_basis(rule.basis) for line in qualifying_lines
            )
            commissionable_sales_amount = sum(
                line.amount_for_basis(rule.basis) for line in commissionable_lines
            )
            m2 = sum(
                (line.quantity or 0.0) * (line.document_sign or 1.0)
                for line in commissionable_lines
            )
            eligible = qualifying_sales_amount >= rule.min_sales_amount
            bonus = max(m2, 0.0) * rule.amount_per_m2 if eligible else 0.0
            result.liquidation_sales += qualifying_sales_amount
            result.liquidation_m2 += m2
            result.liquidation_bonus += bonus
            Detail.create({
                "result_id": result.id,
                "detail_type": "liquidation",
                "description": _(
                    "Promoción por nombre: mínimo %(minimum).2f; ventas para meta %(qualifying).2f; "
                    "base comisionable %(commissionable).2f; m² comisionables %(m2).2f; "
                    "productos coincidentes %(count)s"
                ) % {
                    "minimum": rule.min_sales_amount,
                    "qualifying": qualifying_sales_amount,
                    "commissionable": commissionable_sales_amount,
                    "m2": m2,
                    "count": len(qualifying_lines),
                },
                "location_id": rule.location_id.id or False,
                "basis_amount": commissionable_sales_amount,
                "qualification_amount": qualifying_sales_amount,
                "basis_type": rule.basis,
                "quantity": m2,
                "rate": rule.amount_per_m2,
                "amount": bonus,
                "eligible": eligible,
            })

    def _calculate_manager_commission(
        self,
        result,
        manager,
        commissionable_by_seller,
        qualification_by_seller,
        location_target_status,
        Detail,
    ):
        """Gestión: mínimo con ventas calificables; pago sobre ventas comisionables."""
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
            commissionable_lines = commissionable_by_seller[rule.seller_id.id]
            qualification_lines = qualification_by_seller[rule.seller_id.id]
            commissionable_basis = sum(
                line.amount_for_basis(rule.basis) for line in commissionable_lines
            )
            qualification_basis = sum(
                line.amount_for_basis(rule.basis) for line in qualification_lines
            )

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

            minimum_ok = minimum_available and qualification_basis >= effective_minimum
            status = location_target_status.get(rule.location_id.id)
            location_ok = bool(status and status["met"])
            location_achievement = status["achievement"] if status else 0.0
            eligible = minimum_ok and location_ok
            commission = (
                commissionable_basis * rule.commission_percent / 100.0
                if eligible
                else 0.0
            )

            result.management_sales += commissionable_basis
            result.management_commission += commission
            target_reference = target.target_amount if target else 0.0
            Detail.create({
                "result_id": result.id,
                "detail_type": "management",
                "description": _(
                    "Gestión %(seller)s | ventas para mínimo %(qualifying).2f | "
                    "base comisionable %(commissionable).2f | mínimo admin %(minimum).2f (%(mode)s) | "
                    "meta vendedor %(target).2f | local %(location)s %(achievement).2f%%"
                ) % {
                    "seller": rule.seller_id.name,
                    "qualifying": qualification_basis,
                    "commissionable": commissionable_basis,
                    "minimum": effective_minimum,
                    "mode": minimum_label,
                    "target": target_reference,
                    "location": rule.location_id.display_name,
                    "achievement": location_achievement,
                },
                "managed_seller_id": rule.seller_id.id,
                "location_id": rule.location_id.id,
                "basis_amount": commissionable_basis,
                "qualification_amount": qualification_basis,
                "basis_type": rule.basis,
                "rate": rule.commission_percent,
                "amount": commission,
                "eligible": eligible,
            })

    def _get_liquidation_rule_evaluations(self, seller, seller_sales):
        """Evalúa metas de liquidación sobre ventas de productos promocionales.

        Los productos se identifican por coincidencia del nombre normalizado
        contra la lista cargada en el período. ``Indica_Precio`` ya no participa.
        La regla específica del vendedor prevalece sobre la general por local.
        """
        self.ensure_one()
        rules = self.period_id.liquidation_rule_ids.filtered(
            lambda rule: not rule.seller_id or rule.seller_id == seller
        )
        best_by_location = {}
        for rule in rules.sorted(lambda rule: (bool(rule.seller_id), rule.id)):
            best_by_location[rule.location_id.id or 0] = rule

        evaluations = []
        for rule in best_by_location.values():
            lines = self._promotion_lines_for_rule(seller_sales, rule)
            sales_amount = sum(
                line.amount_for_basis(rule.basis) for line in lines
            )
            evaluations.append({
                "rule": rule,
                "sales": sales_amount,
                "minimum": rule.min_sales_amount,
                "met": sales_amount >= rule.min_sales_amount,
                "matching_lines": len(lines),
            })
        return evaluations

    def _apply_liquidation_commission_penalty(
        self, result, seller, seller_sales, Detail
    ):
        """Resta puntos porcentuales a la tasa ganada por ventas.

        Si el vendedor incumple una meta de liquidación aplicable, la reducción
        configurada se resta DIRECTAMENTE de cada tasa de comisión de ventas
        obtenida (comisión propia y proyectos). Ejemplo: 2,00% - 0,50 p.p.
        = 1,50%. La tasa nunca puede quedar por debajo de 0%.

        No se reduce un porcentaje del valor ya comisionado. La comisión de
        gestión del administrador y el bono de liquidación tampoco se alteran.
        """
        self.ensure_one()
        period = self.period_id
        evaluations = self._get_liquidation_rule_evaluations(
            seller, seller_sales
        )
        if not evaluations:
            return

        unmet = [evaluation for evaluation in evaluations if not evaluation["met"]]
        result.liquidation_target_met = not bool(unmet)
        if not unmet:
            return

        failed_parts = []
        for evaluation in unmet:
            rule = evaluation["rule"]
            location = (
                rule.location_id.display_name
                if rule.location_id
                else _("Todas las localidades")
            )
            failed_parts.append(
                _("%(location)s: %(sales).2f / %(minimum).2f") % {
                    "location": location,
                    "sales": evaluation["sales"],
                    "minimum": evaluation["minimum"],
                }
            )

        is_exempt = seller in period.liquidation_penalty_exempt_seller_ids
        configured_points = period.liquidation_commission_rate_reduction or 0.0
        applied_points = 0.0 if is_exempt else configured_points

        commission_details = result.detail_ids.filtered(
            lambda detail: detail.detail_type in ("standard", "project")
            and (detail.amount or 0.0) > 0.0
            and (detail.rate or 0.0) > 0.0
        )
        original_commission = sum(commission_details.mapped("amount"))
        monetary_reduction = 0.0

        if applied_points > 0.0:
            for detail in commission_details:
                original_rate = detail.rate or 0.0
                detail_reduction = min(applied_points, original_rate)
                effective_rate = max(original_rate - applied_points, 0.0)
                original_amount = detail.amount or 0.0
                effective_amount = (
                    (detail.basis_amount or 0.0) * effective_rate / 100.0
                )
                monetary_reduction += max(
                    original_amount - effective_amount, 0.0
                )
                detail.write({
                    "original_rate": original_rate,
                    "liquidation_rate_reduction": detail_reduction,
                    "rate": effective_rate,
                    "amount": effective_amount,
                    "description": (
                        "%s | %s" % (
                            detail.description or "",
                            _(
                                "Ajuste liquidación: %(original).4f%% - "
                                "%(reduction).4f p.p. = %(effective).4f%%"
                            ) % {
                                "original": original_rate,
                                "reduction": detail_reduction,
                                "effective": effective_rate,
                            },
                        )
                    ).strip(" |"),
                })

            # Los importes principales quedan ya calculados con la tasa efectiva.
            # Por ello el descuento monetario NO se vuelve a restar al total.
            result.standard_commission = sum(
                result.detail_ids.filtered(
                    lambda detail: detail.detail_type == "standard"
                ).mapped("amount")
            )
            result.project_commission = sum(
                result.detail_ids.filtered(
                    lambda detail: detail.detail_type == "project"
                ).mapped("amount")
            )

        result.liquidation_penalty_base = original_commission
        result.liquidation_penalty_percent = 0.0  # campo legado 1.7.x
        result.liquidation_rate_reduction = applied_points
        result.liquidation_penalty = monetary_reduction
        result.liquidation_rate_adjusted = bool(monetary_reduction)
        result.liquidation_penalty_applied = bool(monetary_reduction)

        if is_exempt:
            description = _(
                "Meta de liquidación no cumplida, pero el vendedor está exento "
                "del ajuste de tasa. Metas incumplidas: %(failed)s"
            ) % {"failed": "; ".join(failed_parts)}
        elif configured_points <= 0.0:
            description = _(
                "Meta de liquidación no cumplida. La reducción de tasa está "
                "configurada en 0 p.p. Metas incumplidas: %(failed)s"
            ) % {"failed": "; ".join(failed_parts)}
        else:
            adjusted_commission = max(
                original_commission - monetary_reduction, 0.0
            )
            description = _(
                "Meta de liquidación no cumplida. Se restan %(points).4f puntos "
                "porcentuales a cada tasa de comisión propia/proyecto, sin bajar "
                "de 0%%. Comisión antes del ajuste %(before).2f; después %(after).2f; "
                "reducción monetaria %(amount).2f. Metas incumplidas: %(failed)s"
            ) % {
                "points": configured_points,
                "before": original_commission,
                "after": adjusted_commission,
                "amount": monetary_reduction,
                "failed": "; ".join(failed_parts),
            }

        # Línea informativa: el importe de la reducción ya está incorporado en
        # las líneas standard/project mediante su nueva tasa efectiva; por eso
        # aquí amount=0 evita descontarlo una segunda vez en cualquier auditoría.
        Detail.create({
            "result_id": result.id,
            "detail_type": "liquidation_penalty",
            "description": description,
            "basis_amount": original_commission,
            "rate": applied_points,
            "amount": 0.0,
            "eligible": False,
        })

    def _rebuild_dashboard_lines(self, sales=None, exclusion_by_sale=None):
        """Create an auditable analytical snapshot for graph/pivot dashboards.

        Sales rows carry sales measures once. Commission rows carry commission
        measures only, so pivot totals do not duplicate sales when components are
        grouped. Commission attribution follows the final effective rates after
        the liquidation adjustment.
        """
        self.ensure_one()
        Dashboard = self.env["commission.dashboard.line"]
        Sale = self.env["commission.sale"]
        Dashboard.sudo().search([("settlement_id", "=", self.id)]).unlink()

        sales = sales if sales is not None else Sale.search(self._sale_domain())
        commissionable_sales, qualification_sales, computed_exclusions = (
            self.period_id._classify_sales_by_client_exclusion(sales)
        )
        exclusion_by_sale = exclusion_by_sale or computed_exclusions
        commissionable_ids = set(commissionable_sales.ids)
        qualification_ids = set(qualification_sales.ids)
        commissionable_by_seller = defaultdict(lambda: Sale.browse())
        for sale in commissionable_sales:
            commissionable_by_seller[sale.seller_id.id] |= sale

        vals_list = []

        def dimensions(sale):
            return {
                "period_id": self.period_id.id,
                "period_month": self.period_id.date_start,
                "source_seller_id": sale.seller_id.id,
                "sale_id": sale.id,
                "location_id": sale.location_id.id or False,
                "warehouse": sale.warehouse or False,
                "product_line": sale.product_line or False,
                "origin": sale.origin or False,
                "client": sale.client or False,
            }

        # Base sales rows.
        for sale in sales:
            exclusion = exclusion_by_sale.get(sale.id)
            net = sale.amount_for_basis("net")
            vals = dimensions(sale)
            vals.update({
                "settlement_id": self.id,
                "commission_recipient_id": sale.seller_id.id,
                "component": "sales",
                "sale_count": 1,
                "gross_sales": net,
                "target_sales": net if sale.id in qualification_ids else 0.0,
                "commissionable_sales": net if sale.id in commissionable_ids else 0.0,
                "commission_amount": 0.0,
                "quantity": (sale.quantity or 0.0) * (sale.document_sign or 1.0),
                "client_excluded": bool(exclusion),
                "counts_for_target": bool(exclusion and exclusion.count_for_target),
            })
            vals_list.append(vals)

        for result in self.result_ids:
            seller_lines = commissionable_by_seller[result.seller_id.id]
            for detail in result.detail_ids.filtered(
                lambda d: d.detail_type in ("standard", "project", "management", "liquidation")
                and d.eligible
                and (d.amount or 0.0) != 0.0
            ):
                lines = Sale.browse()
                if detail.detail_type == "standard":
                    lines = seller_lines
                elif detail.detail_type == "project":
                    origin_key = (detail.project_origin or "").strip().lower()
                    lines = seller_lines.filtered(
                        lambda sale: (sale.origin or "").strip().lower() == origin_key
                    )
                elif detail.detail_type == "management" and detail.managed_seller_id:
                    lines = commissionable_by_seller[detail.managed_seller_id.id]
                elif detail.detail_type == "liquidation":
                    promo_names = self._promotion_name_set()
                    lines = seller_lines.filtered(
                        lambda sale: (
                            (sale.promotion_match_name or normalize_product_name(sale.product_name)) in promo_names
                            and (not detail.location_id or sale.location_id == detail.location_id)
                        )
                    )

                for sale in lines:
                    if detail.detail_type == "liquidation":
                        commission_amount = (
                            (sale.quantity or 0.0)
                            * (sale.document_sign or 1.0)
                            * (detail.rate or 0.0)
                        )
                    else:
                        basis = detail.basis_type or "net"
                        commission_amount = sale.amount_for_basis(basis) * (detail.rate or 0.0) / 100.0
                    if not commission_amount:
                        continue
                    vals = dimensions(sale)
                    vals.update({
                        "settlement_id": self.id,
                        "result_id": result.id,
                        "commission_recipient_id": result.seller_id.id,
                        "component": detail.detail_type,
                        "commission_amount": commission_amount,
                        "rate": detail.rate,
                        "quantity": (
                            (sale.quantity or 0.0) * (sale.document_sign or 1.0)
                            if detail.detail_type == "liquidation" else 0.0
                        ),
                    })
                    vals_list.append(vals)

        if vals_list:
            Dashboard.sudo().create(vals_list)
        return True

    def action_rebuild_dashboard(self):
        for settlement in self:
            settlement._rebuild_dashboard_lines()
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Dashboard de comisiones"),
                "message": _("La analítica del período fue reconstruida correctamente."),
                "type": "success",
                "sticky": False,
            },
        }

    def action_print_settlement(self):
        self.ensure_one()
        return self.env.ref(
            "transcash_commission_goal_rules.action_report_commission_settlement_total"
        ).report_action(self)


class CommissionResult(models.Model):
    _inherit = "commission.result"

    gross_sales_before_client_exclusions = fields.Float(
        string="Ventas antes de exclusiones de cliente", digits=(16, 4)
    )
    qualification_sales = fields.Float(
        string="Ventas consideradas para metas", digits=(16, 4)
    )
    excluded_client_sales = fields.Float(
        string="Ventas excluidas por cliente", digits=(16, 4)
    )
    excluded_client_line_count = fields.Integer(
        string="Líneas excluidas por cliente"
    )

    liquidation_target_met = fields.Boolean(
        string="Cumple meta liquidación",
        default=True,
    )
    liquidation_penalty_base = fields.Float(
        string="Comisión antes del ajuste de tasa",
        digits=(16, 4),
    )
    liquidation_penalty_percent = fields.Float(
        string="Reducción sobre comisión (%) [legado]",
        digits=(16, 4),
        help="Campo histórico de versiones 1.7.x.",
    )
    liquidation_rate_reduction = fields.Float(
        string="Reducción de tasa liquidación (p.p.)",
        digits=(16, 4),
    )
    liquidation_penalty = fields.Float(
        string="Reducción monetaria (ya aplicada)",
        digits=(16, 4),
    )
    liquidation_rate_adjusted = fields.Boolean(
        string="Tasa ajustada directamente",
        help=(
            "Indica que la reducción monetaria ya está incorporada en las tasas "
            "efectivas de comisión y no debe restarse nuevamente al total."
        ),
    )
    liquidation_penalty_applied = fields.Boolean(
        string="Reducción aplicada",
    )

    def _recompute_total(self):
        res = super()._recompute_total()
        for rec in self:
            # Compatibilidad con liquidaciones históricas 1.7.x: esas versiones
            # calculaban primero la comisión completa y luego restaban un monto.
            # Las nuevas liquidaciones ya guardan standard/project con tasa neta.
            if rec.liquidation_penalty and not rec.liquidation_rate_adjusted:
                rec.total_commission -= rec.liquidation_penalty
        return res

    def action_print_individual(self):
        self.ensure_one()
        return self.env.ref(
            "transcash_commission_goal_rules.action_report_commission_result_individual"
        ).report_action(self)


class CommissionResultDetail(models.Model):
    _inherit = "commission.result.detail"

    qualification_amount = fields.Float(
        string="Base para meta / mínimo",
        digits=(16, 4),
        help="Base usada para validar el rango/meta cuando puede incluir clientes excluidos que cuentan para cumplimiento.",
    )
    basis_type = fields.Selection(
        [("net", "Total neto"), ("price", "Total precio"), ("margin", "Utilidad")],
        string="Base de cálculo",
    )
    project_origin = fields.Char(string="Origen proyecto")

    detail_type = fields.Selection(
        selection_add=[
            ("liquidation_penalty", "Reducción por meta de liquidación"),
        ],
        ondelete={"liquidation_penalty": "cascade"},
    )
    original_rate = fields.Float(
        string="Tasa original (%)",
        digits=(16, 4),
        help="Tasa antes de aplicar la reducción por incumplir liquidación.",
    )
    liquidation_rate_reduction = fields.Float(
        string="Reducción de tasa (p.p.)",
        digits=(16, 4),
    )
