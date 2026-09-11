import base64
from datetime import timedelta

from odoo import Command
from odoo.tests.common import TransactionCase


class TestCommissionGoalRules(TransactionCase):
    def setUp(self):
        super().setUp()
        self.Seller = self.env["commission.seller"]
        self.Location = self.env["commission.location"]
        self.Sale = self.env["commission.sale"]
        self.Period = self.env["commission.period"]

        self.loc_a = self.Location.create({"code": "GR-A", "name": "Local A"})
        self.loc_b = self.Location.create({"code": "GR-B", "name": "Local B"})
        self.manager = self.Seller.create({
            "code": "GR-ADM",
            "name": "Administrador",
            "role": "manager",
        })
        self.seller_1 = self.Seller.create({
            "code": "GR-V1",
            "name": "Vendedor 1",
            "role": "seller",
            "manager_id": self.manager.id,
        })
        self.seller_2 = self.Seller.create({
            "code": "GR-S2",
            "name": "Vendedor 2",
            "role": "seller",
            "manager_id": self.manager.id,
        })
        self.project_seller = self.Seller.create({
            "code": "GR-PROY",
            "name": "Vendedor Proyecto",
            "role": "project",
        })
        self.no_target = self.Seller.create({
            "code": "GR-SIN",
            "name": "Sin Meta",
            "role": "seller",
        })
        self.period = self.Period.create({
            "name": "Prueba metas y gestión",
            "date_start": "2026-05-01",
            "date_end": "2026-05-31",
        })

    def _target(self, seller, amount=1000.0, rate=0.0):
        target = self.env["commission.seller.target"].create({
            "period_id": self.period.id,
            "seller_id": seller.id,
            "target_amount": amount,
            "basis": "net",
        })
        self.env["commission.seller.target.tier"].create({
            "target_id": target.id,
            "min_achievement": 0.0,
            "commission_percent": rate,
        })
        return target

    def _sale(
        self, code, seller, location, net, origin=None, price_indicator=0.0,
        quantity=1.0, product_name=None
    ):
        return self.Sale.create({
            "fingerprint": code,
            "registration_date": "2026-05-10",
            "seller_id": seller.id,
            "location_id": location.id,
            "document_type": "FA",
            "number": code,
            "invoice": code,
            "product_code": code,
            "product_name": product_name or code,
            "origin": origin or "",
            "price_indicator": price_indicator,
            "quantity": quantity,
            "total_price": net,
            "total_net": net,
            "profit": net * 0.30,
            "document_sign": 1.0,
        })

    def _promotion(self, name, code="CORTADO"):
        return self.env["commission.period.promotion.product"].create({
            "period_id": self.period.id,
            "product_name": name,
            "source_code": code,
        })

    def _location_target(self, amount=1000.0):
        return self.env["commission.location.target"].create({
            "period_id": self.period.id,
            "location_id": self.loc_a.id,
            "target_amount": amount,
            "basis": "net",
            "required_achievement": 100.0,
        })

    def _management(self, lines):
        commands = []
        for vals in lines:
            commands.append((0, 0, vals))
        return self.env["commission.manager.goal.rule"].create({
            "period_id": self.period.id,
            "manager_id": self.manager.id,
            "location_id": self.loc_a.id,
            "line_ids": commands,
        })

    def test_seller_target_uses_all_locations(self):
        target = self._target(self.seller_1, amount=1000.0, rate=2.0)
        self.assertFalse(target.location_id)
        self._sale("GR-A1", self.seller_1, self.loc_a, 400.0)
        self._sale("GR-B1", self.seller_1, self.loc_b, 600.0)

        settlement = self.env["commission.settlement"].create_or_recalculate(self.period)
        result = settlement.result_ids.filtered(lambda r: r.seller_id == self.seller_1)
        self.assertAlmostEqual(result.standard_sales, 1000.0, places=4)
        self.assertAlmostEqual(result.achievement_percent, 100.0, places=4)
        self.assertAlmostEqual(result.standard_commission, 20.0, places=4)

    def test_seller_without_target_is_not_listed(self):
        self._target(self.seller_1)
        self._sale("GR-T1", self.seller_1, self.loc_a, 100.0)
        self._sale("GR-NT1", self.no_target, self.loc_a, 5000.0)

        settlement = self.env["commission.settlement"].create_or_recalculate(self.period)
        sellers = settlement.result_ids.mapped("seller_id")
        self.assertIn(self.seller_1, sellers)
        self.assertNotIn(self.no_target, sellers)

    def test_project_seller_without_retail_target_is_listed(self):
        self.env["commission.project.rule"].create({
            "period_id": self.period.id,
            "seller_id": self.project_seller.id,
            "origin": "Importado",
            "basis": "net",
            "commission_percent": 2.0,
            "active": True,
        })
        self._sale(
            "GR-PROY-1", self.project_seller, self.loc_a, 1000.0, origin="Importado"
        )

        settlement = self.env["commission.settlement"].create_or_recalculate(self.period)
        result = settlement.result_ids.filtered(
            lambda r: r.seller_id == self.project_seller
        )
        self.assertTrue(result)
        self.assertAlmostEqual(result.standard_commission, 0.0, places=4)
        self.assertAlmostEqual(result.project_commission, 20.0, places=4)

    def test_manager_with_management_parameter_does_not_need_own_target(self):
        self._target(self.seller_1, amount=1000.0, rate=0.0)
        self._location_target(amount=500.0)
        self._management([{
            "seller_id": self.seller_1.id,
            "minimum_type": "fixed",
            "minimum_amount": 500.0,
            "commission_percent": 1.0,
            "basis": "net",
        }])
        self._sale("GR-MGR-1", self.seller_1, self.loc_a, 600.0)

        settlement = self.env["commission.settlement"].create_or_recalculate(self.period)
        result = settlement.result_ids.filtered(lambda r: r.seller_id == self.manager)
        self.assertTrue(result)
        self.assertAlmostEqual(result.management_commission, 6.0, places=4)

    def test_one_management_header_has_multiple_sellers(self):
        self._target(self.seller_1, 1000.0)
        self._target(self.seller_2, 2000.0)
        management = self._management([
            {
                "seller_id": self.seller_1.id,
                "minimum_type": "fixed",
                "minimum_amount": 600.0,
                "commission_percent": 1.0,
                "basis": "net",
            },
            {
                "seller_id": self.seller_2.id,
                "minimum_type": "target_percent",
                "minimum_target_percent": 75.0,
                "commission_percent": 1.5,
                "basis": "net",
            },
        ])
        self.assertEqual(len(management.line_ids), 2)
        self.assertEqual(management.line_ids.mapped("manager_id"), self.manager)
        self.assertEqual(management.line_ids.mapped("location_id"), self.loc_a)
        self.assertAlmostEqual(
            management.line_ids.filtered(lambda l: l.seller_id == self.seller_2).effective_minimum,
            1500.0,
            places=4,
        )

    def test_manager_fixed_minimum_is_independent_from_seller_target(self):
        self._target(self.manager, amount=100.0, rate=0.0)
        self._target(self.seller_1, amount=1000.0, rate=0.0)
        self._location_target(amount=500.0)
        self._management([{
            "seller_id": self.seller_1.id,
            "minimum_type": "fixed",
            "minimum_amount": 600.0,
            "commission_percent": 1.0,
            "basis": "net",
        }])

        # 70% de su meta propia, pero supera el mínimo ADMIN de 600.
        self._sale("GR-F1A", self.seller_1, self.loc_a, 500.0)
        self._sale("GR-F1B", self.seller_1, self.loc_b, 200.0)

        settlement = self.env["commission.settlement"].create_or_recalculate(self.period)
        manager_result = settlement.result_ids.filtered(lambda r: r.seller_id == self.manager)
        self.assertAlmostEqual(manager_result.management_commission, 7.0, places=4)

    def test_manager_minimum_can_be_percent_of_seller_target(self):
        self._target(self.manager, amount=100.0, rate=0.0)
        self._target(self.seller_1, amount=1000.0, rate=0.0)
        self._location_target(amount=600.0)
        management = self._management([{
            "seller_id": self.seller_1.id,
            "minimum_type": "target_percent",
            "minimum_target_percent": 80.0,
            "commission_percent": 1.5,
            "basis": "net",
        }])
        rule = management.line_ids
        self.assertAlmostEqual(rule.effective_minimum, 800.0, places=4)

        self._sale("GR-P1A", self.seller_1, self.loc_a, 600.0)
        self._sale("GR-P1B", self.seller_1, self.loc_b, 250.0)

        settlement = self.env["commission.settlement"].create_or_recalculate(self.period)
        manager_result = settlement.result_ids.filtered(lambda r: r.seller_id == self.manager)
        self.assertAlmostEqual(manager_result.management_commission, 12.75, places=4)

    def test_manager_commission_requires_location_target(self):
        self._target(self.manager, amount=100.0, rate=0.0)
        self._target(self.seller_1, amount=1000.0, rate=0.0)
        self._location_target(amount=1000.0)
        self._management([{
            "seller_id": self.seller_1.id,
            "minimum_type": "fixed",
            "minimum_amount": 500.0,
            "commission_percent": 1.0,
            "basis": "net",
        }])
        self._sale("GR-L1A", self.seller_1, self.loc_a, 400.0)
        self._sale("GR-L1B", self.seller_1, self.loc_b, 400.0)

        settlement = self.env["commission.settlement"].create_or_recalculate(self.period)
        manager_result = settlement.result_ids.filtered(lambda r: r.seller_id == self.manager)
        self.assertAlmostEqual(manager_result.management_commission, 0.0, places=4)

    def test_reports_are_available(self):
        self._target(self.seller_1)
        settlement = self.env["commission.settlement"].create_or_recalculate(self.period)
        result = settlement.result_ids.filtered(lambda r: r.seller_id == self.seller_1)
        self.assertEqual(settlement.action_print_settlement()["type"], "ir.actions.report")
        self.assertEqual(result.action_print_individual()["type"], "ir.actions.report")

    def test_selecting_manager_loads_related_sellers(self):
        management = self.env["commission.manager.goal.rule"].new({
            "period_id": self.period.id,
            "location_id": self.loc_a.id,
        })
        management.manager_id = self.manager
        management._onchange_manager_id_load_sellers()
        self.assertEqual(
            set(management.line_ids.mapped("seller_id").ids),
            {self.seller_1.id, self.seller_2.id},
        )

    def test_create_management_without_lines_loads_related_sellers(self):
        management = self.env["commission.manager.goal.rule"].create({
            "period_id": self.period.id,
            "manager_id": self.manager.id,
            "location_id": self.loc_a.id,
        })
        self.assertEqual(
            set(management.line_ids.mapped("seller_id").ids),
            {self.seller_1.id, self.seller_2.id},
        )

    def test_duplicate_period_copies_all_goal_parameters(self):
        target = self._target(self.seller_1, amount=1500.0, rate=2.0)
        self._location_target(amount=5000.0)
        management = self._management([{
            "seller_id": self.seller_1.id,
            "minimum_type": "fixed",
            "minimum_amount": 600.0,
            "commission_percent": 0.75,
            "basis": "net",
        }])
        project_rule = self.env["commission.project.rule"].create({
            "period_id": self.period.id,
            "seller_id": self.project_seller.id,
            "origin": "Importado",
            "basis": "net",
            "commission_percent": 1.25,
            "active": True,
        })
        liquidation_rule = self.env["commission.liquidation.rule"].create({
            "period_id": self.period.id,
            "seller_id": self.seller_1.id,
            "location_id": self.loc_a.id,
            "indicator_value": 3.0,
            "min_sales_amount": 200.0,
            "amount_per_m2": 0.25,
            "basis": "net",
        })
        promotion = self._promotion("CERÁMICA PROMO 60X60", code="00123")

        new_period = self.period.copy()

        self.assertEqual(new_period.state, "draft")
        self.assertEqual(new_period.date_start.isoformat(), "2026-06-01")
        self.assertEqual(new_period.date_end.isoformat(), "2026-06-30")
        self.assertFalse(new_period.settlement_id)
        self.assertEqual(len(new_period.target_ids), 1)
        self.assertEqual(new_period.target_ids.seller_id, self.seller_1)
        self.assertEqual(new_period.target_ids.target_amount, target.target_amount)
        self.assertEqual(len(new_period.target_ids.tier_ids), len(target.tier_ids))
        self.assertEqual(len(new_period.project_rule_ids), 1)
        self.assertEqual(new_period.project_rule_ids.seller_id, project_rule.seller_id)
        self.assertEqual(new_period.project_rule_ids.origin, project_rule.origin)
        self.assertEqual(len(new_period.location_target_ids), 1)
        self.assertEqual(len(new_period.manager_goal_rule_ids), 1)
        copied_management = new_period.manager_goal_rule_ids
        self.assertEqual(copied_management.manager_id, management.manager_id)
        self.assertEqual(copied_management.location_id, management.location_id)
        self.assertEqual(len(copied_management.line_ids), 1)
        self.assertAlmostEqual(copied_management.line_ids.commission_percent, 0.75, places=4)
        self.assertEqual(len(new_period.liquidation_rule_ids), 1)
        self.assertAlmostEqual(
            new_period.liquidation_rule_ids.amount_per_m2,
            liquidation_rule.amount_per_m2,
            places=4,
        )
        self.assertEqual(len(new_period.promotion_product_ids), 1)
        self.assertEqual(new_period.promotion_product_ids.product_name, promotion.product_name)
        self.assertFalse(new_period.promotion_file)

    def test_copy_single_target_to_other_period(self):
        target = self._target(self.seller_1, amount=1200.0, rate=1.5)
        destination = self.Period.create({
            "name": "Destino copia",
            "date_start": "2026-06-01",
            "date_end": "2026-06-30",
        })
        copied = target.copy_to_period(destination)
        self.assertEqual(copied.period_id, destination)
        self.assertEqual(copied.seller_id, self.seller_1)
        self.assertAlmostEqual(copied.target_amount, 1200.0, places=4)
        self.assertEqual(len(copied.tier_ids), 1)

    def test_duplicate_seller_target_same_period_is_blocked(self):
        self._target(self.seller_1, amount=1000.0)
        with self.assertRaises(Exception):
            self.env["commission.seller.target"].create({
                "period_id": self.period.id,
                "seller_id": self.seller_1.id,
                "target_amount": 2000.0,
                "basis": "net",
            })

    def test_legacy_proportional_input_is_forced_to_sales_tier(self):
        target = self.env["commission.seller.target"].create({
            "period_id": self.period.id,
            "seller_id": self.seller_1.id,
            "target_amount": 35000.0,
            "basis": "net",
            "calculation_mode": "proportional",
            "minimum_achievement": 80.0,
            "full_commission_percent": 2.0,
        })
        self.assertEqual(target.calculation_mode, "sales_tier")

    def test_sales_tier_sets_legacy_required_achievement_automatically(self):
        target = self.env["commission.seller.target"].create({
            "period_id": self.period.id,
            "seller_id": self.seller_1.id,
            "target_amount": 20000.0,
            "basis": "net",
            "calculation_mode": "sales_tier",
        })
        tier = self.env["commission.seller.target.tier"].create({
            "target_id": target.id,
            "sales_threshold": 10000.0,
            "commission_percent": 1.0,
        })
        self.assertEqual(tier.min_achievement, 0.0)
        self.assertEqual(tier.max_achievement, 0.0)

    def test_sales_tier_inline_one2many_create_sets_legacy_required_field(self):
        target = self.env["commission.seller.target"].create({
            "period_id": self.period.id,
            "seller_id": self.seller_1.id,
            "target_amount": 20000.0,
            "basis": "net",
            "calculation_mode": "sales_tier",
            "tier_ids": [Command.create({
                "sales_threshold": 10000.0,
                "commission_percent": 1.0,
            })],
        })
        self.assertEqual(len(target.tier_ids), 1)
        self.assertEqual(target.tier_ids.min_achievement, 0.0)
        self.assertEqual(target.tier_ids.max_achievement, 0.0)

    def test_sales_tier_copy_keeps_legacy_required_field_valid(self):
        target = self.env["commission.seller.target"].create({
            "period_id": self.period.id,
            "seller_id": self.seller_1.id,
            "target_amount": 20000.0,
            "basis": "net",
            "calculation_mode": "sales_tier",
        })
        tier = self.env["commission.seller.target.tier"].create({
            "target_id": target.id,
            "sales_threshold": 10000.0,
            "commission_percent": 1.0,
        })
        copied = tier.copy({"sales_threshold": 15000.0})
        self.assertEqual(copied.min_achievement, 0.0)
        self.assertEqual(copied.max_achievement, 0.0)

    def test_sales_tiers_apply_last_reached_threshold(self):
        target = self.env["commission.seller.target"].create({
            "period_id": self.period.id,
            "seller_id": self.seller_1.id,
            "target_amount": 20000.0,
            "basis": "net",
            "calculation_mode": "sales_tier",
        })
        Tier = self.env["commission.seller.target.tier"]
        Tier.create({
            "target_id": target.id,
            "sales_threshold": 10000.0,
            "commission_percent": 1.0,
        })
        Tier.create({
            "target_id": target.id,
            "sales_threshold": 15000.0,
            "commission_percent": 1.5,
        })
        Tier.create({
            "target_id": target.id,
            "sales_threshold": 20000.0,
            "commission_percent": 2.0,
        })
        self._sale("GR-TIER-AMOUNT", self.seller_1, self.loc_a, 17000.0)

        settlement = self.env["commission.settlement"].create_or_recalculate(self.period)
        result = settlement.result_ids.filtered(lambda r: r.seller_id == self.seller_1)
        self.assertAlmostEqual(result.standard_commission, 255.0, places=4)
        detail = result.detail_ids.filtered(lambda d: d.detail_type == "standard")
        self.assertAlmostEqual(detail.rate, 1.5, places=4)
        self.assertTrue(detail.eligible)

    def test_sales_tiers_pay_zero_below_first_threshold(self):
        target = self.env["commission.seller.target"].create({
            "period_id": self.period.id,
            "seller_id": self.seller_1.id,
            "target_amount": 15000.0,
            "basis": "net",
            "calculation_mode": "sales_tier",
        })
        self.env["commission.seller.target.tier"].create({
            "target_id": target.id,
            "sales_threshold": 10000.0,
            "commission_percent": 1.0,
        })
        self._sale("GR-TIER-BELOW", self.seller_1, self.loc_a, 9999.0)

        settlement = self.env["commission.settlement"].create_or_recalculate(self.period)
        result = settlement.result_ids.filtered(lambda r: r.seller_id == self.seller_1)
        self.assertAlmostEqual(result.standard_commission, 0.0, places=4)
        detail = result.detail_ids.filtered(lambda d: d.detail_type == "standard")
        self.assertAlmostEqual(detail.rate, 0.0, places=4)
        self.assertFalse(detail.eligible)

    def test_sales_tier_duplicate_threshold_is_blocked(self):
        target = self.env["commission.seller.target"].create({
            "period_id": self.period.id,
            "seller_id": self.seller_1.id,
            "target_amount": 15000.0,
            "basis": "net",
            "calculation_mode": "sales_tier",
        })
        Tier = self.env["commission.seller.target.tier"]
        Tier.create({
            "target_id": target.id,
            "sales_threshold": 10000.0,
            "commission_percent": 1.0,
        })
        with self.assertRaises(Exception):
            Tier.create({
                "target_id": target.id,
                "sales_threshold": 10000.0,
                "commission_percent": 1.5,
            })

    def test_duplicate_period_copies_sales_thresholds(self):
        target = self.env["commission.seller.target"].create({
            "period_id": self.period.id,
            "seller_id": self.seller_1.id,
            "target_amount": 20000.0,
            "basis": "net",
            "calculation_mode": "sales_tier",
        })
        self.env["commission.seller.target.tier"].create({
            "target_id": target.id,
            "sales_threshold": 10000.0,
            "commission_percent": 1.0,
        })
        self.env["commission.seller.target.tier"].create({
            "target_id": target.id,
            "sales_threshold": 15000.0,
            "commission_percent": 1.5,
        })

        new_period = self.period.copy()
        copied = new_period.target_ids.filtered(lambda t: t.seller_id == self.seller_1)
        self.assertEqual(copied.calculation_mode, "sales_tier")
        self.assertEqual(len(copied.tier_ids), 2)
        self.assertEqual(
            sorted(copied.tier_ids.mapped("sales_threshold")),
            [10000.0, 15000.0],
        )

    def test_liquidation_target_failure_reduces_seller_commission(self):
        target = self.env["commission.seller.target"].create({
            "period_id": self.period.id,
            "seller_id": self.seller_1.id,
            "target_amount": 1000.0,
            "basis": "net",
            "calculation_mode": "sales_tier",
        })
        self.env["commission.seller.target.tier"].create({
            "target_id": target.id,
            "sales_threshold": 0.0,
            "commission_percent": 2.0,
        })
        self.period.liquidation_commission_rate_reduction = 0.5
        self._promotion("CERAMICA PROMO GR-LP")
        self.env["commission.liquidation.rule"].create({
            "period_id": self.period.id,
            "seller_id": self.seller_1.id,
            "indicator_value": 3.0,
            "min_sales_amount": 200.0,
            "amount_per_m2": 0.30,
            "basis": "net",
        })
        # Indica_Precio=3 en un producto NO promocional ya no lo incluye.
        self._sale(
            "GR-LP-NORMAL", self.seller_1, self.loc_a, 900.0,
            price_indicator=3.0, product_name="PRODUCTO NORMAL"
        )
        # El producto promocional sí entra aun con Indica_Precio=0.
        self._sale(
            "GR-LP-LIQ", self.seller_1, self.loc_a, 100.0,
            price_indicator=0.0, quantity=10.0, product_name="Cerámica Promo GR LP"
        )

        settlement = self.env["commission.settlement"].create_or_recalculate(self.period)
        result = settlement.result_ids.filtered(lambda r: r.seller_id == self.seller_1)

        self.assertAlmostEqual(result.standard_commission, 15.0, places=4)
        self.assertFalse(result.liquidation_target_met)
        self.assertAlmostEqual(result.liquidation_penalty_base, 20.0, places=4)
        self.assertAlmostEqual(result.liquidation_rate_reduction, 0.5, places=4)
        self.assertAlmostEqual(result.liquidation_penalty, 5.0, places=4)
        self.assertAlmostEqual(result.liquidation_bonus, 0.0, places=4)
        self.assertAlmostEqual(result.total_commission, 15.0, places=4)
        detail = result.detail_ids.filtered(
            lambda d: d.detail_type == "liquidation_penalty"
        )
        self.assertTrue(detail)
        self.assertAlmostEqual(detail.amount, 0.0, places=4)
        standard_detail = result.detail_ids.filtered(lambda d: d.detail_type == "standard")
        self.assertAlmostEqual(standard_detail.original_rate, 2.0, places=4)
        self.assertAlmostEqual(standard_detail.rate, 1.5, places=4)
        self.assertAlmostEqual(standard_detail.amount, 15.0, places=4)

    def test_liquidation_penalty_exempt_seller_is_not_reduced(self):
        target = self.env["commission.seller.target"].create({
            "period_id": self.period.id,
            "seller_id": self.seller_1.id,
            "target_amount": 1000.0,
            "basis": "net",
            "calculation_mode": "sales_tier",
        })
        self.env["commission.seller.target.tier"].create({
            "target_id": target.id,
            "sales_threshold": 0.0,
            "commission_percent": 2.0,
        })
        self.period.write({
            "liquidation_commission_rate_reduction": 0.5,
            "liquidation_penalty_exempt_seller_ids": [(6, 0, [self.seller_1.id])],
        })
        self._promotion("PROMO EXENTA")
        self.env["commission.liquidation.rule"].create({
            "period_id": self.period.id,
            "seller_id": self.seller_1.id,
            "indicator_value": 3.0,
            "min_sales_amount": 200.0,
            "amount_per_m2": 0.30,
            "basis": "net",
        })
        self._sale("GR-EX-NORMAL", self.seller_1, self.loc_a, 900.0)
        self._sale(
            "GR-EX-LIQ", self.seller_1, self.loc_a, 100.0,
            price_indicator=0.0, quantity=10.0, product_name="Promo Exenta",
        )

        settlement = self.env["commission.settlement"].create_or_recalculate(self.period)
        result = settlement.result_ids.filtered(lambda r: r.seller_id == self.seller_1)

        self.assertFalse(result.liquidation_target_met)
        self.assertAlmostEqual(result.liquidation_penalty, 0.0, places=4)
        self.assertAlmostEqual(result.total_commission, 20.0, places=4)
        detail = result.detail_ids.filtered(
            lambda d: d.detail_type == "liquidation_penalty"
        )
        self.assertTrue(detail)
        self.assertIn("exento", detail.description.lower())

    def test_liquidation_target_met_does_not_reduce_commission(self):
        target = self.env["commission.seller.target"].create({
            "period_id": self.period.id,
            "seller_id": self.seller_1.id,
            "target_amount": 1000.0,
            "basis": "net",
            "calculation_mode": "sales_tier",
        })
        self.env["commission.seller.target.tier"].create({
            "target_id": target.id,
            "sales_threshold": 0.0,
            "commission_percent": 2.0,
        })
        self.period.liquidation_commission_rate_reduction = 0.5
        self._promotion("PROMO META CUMPLIDA")
        self.env["commission.liquidation.rule"].create({
            "period_id": self.period.id,
            "seller_id": self.seller_1.id,
            "indicator_value": 3.0,
            "min_sales_amount": 200.0,
            "amount_per_m2": 0.30,
            "basis": "net",
        })
        self._sale("GR-MET-NORMAL", self.seller_1, self.loc_a, 800.0)
        self._sale(
            "GR-MET-LIQ", self.seller_1, self.loc_a, 200.0,
            price_indicator=0.0, quantity=10.0, product_name="Promo Meta Cumplida",
        )

        settlement = self.env["commission.settlement"].create_or_recalculate(self.period)
        result = settlement.result_ids.filtered(lambda r: r.seller_id == self.seller_1)

        self.assertTrue(result.liquidation_target_met)
        self.assertAlmostEqual(result.liquidation_penalty, 0.0, places=4)
        self.assertAlmostEqual(result.liquidation_bonus, 3.0, places=4)
        self.assertAlmostEqual(result.total_commission, 23.0, places=4)

    def test_liquidation_failure_reduces_project_rate_in_percentage_points(self):
        self.seller_1.role = "project"
        self.period.liquidation_commission_rate_reduction = 0.25
        self._promotion("PROMO SIN VENTA")
        self.env["commission.project.rule"].create({
            "period_id": self.period.id,
            "seller_id": self.seller_1.id,
            "origin": "Importado",
            "commission_percent": 1.5,
            "basis": "net",
            "active": True,
        })
        self.env["commission.liquidation.rule"].create({
            "period_id": self.period.id,
            "seller_id": self.seller_1.id,
            "indicator_value": 3.0,
            "min_sales_amount": 200.0,
            "amount_per_m2": 0.30,
            "basis": "net",
        })
        self._sale(
            "GR-PROJ-RATE", self.seller_1, self.loc_a, 1000.0,
            origin="Importado",
        )

        settlement = self.env["commission.settlement"].create_or_recalculate(self.period)
        result = settlement.result_ids.filtered(lambda r: r.seller_id == self.seller_1)

        # 1.50% - 0.25 p.p. = 1.25%; 1,000 x 1.25% = 12.50
        self.assertFalse(result.liquidation_target_met)
        self.assertAlmostEqual(result.project_commission, 12.5, places=4)
        self.assertAlmostEqual(result.liquidation_penalty, 2.5, places=4)
        self.assertAlmostEqual(result.total_commission, 12.5, places=4)
        project_detail = result.detail_ids.filtered(lambda d: d.detail_type == "project")
        self.assertAlmostEqual(project_detail.original_rate, 1.5, places=4)
        self.assertAlmostEqual(project_detail.rate, 1.25, places=4)

    def test_promotion_csv_import_uses_name_and_ignores_truncated_code(self):
        content = (
            "Codproducto;Descripción Producto\n"
            "002006;CERÁMICA CSL CUBIC GREY C1 (27*45) 1.70 M2\n"
            "002;OTRO PRODUCTO\n"
        ).encode("utf-8")
        self.period.write({
            "promotion_filename": "promociones.csv",
            "promotion_file": base64.b64encode(content),
        })
        self.period.action_import_promotion_products()
        self.assertEqual(self.period.promotion_product_count, 2)
        promo = self.period.promotion_product_ids.filtered(
            lambda p: "CUBIC GREY" in p.product_name
        )
        self.assertTrue(promo)
        self.assertEqual(promo.source_code, "002006")

    def test_liquidation_requires_promotion_list_when_rules_exist(self):
        self._target(self.seller_1, amount=1000.0, rate=1.0)
        self.env["commission.liquidation.rule"].create({
            "period_id": self.period.id,
            "seller_id": self.seller_1.id,
            "min_sales_amount": 100.0,
            "amount_per_m2": 0.2,
            "basis": "net",
        })
        self._sale("GR-NO-PROMO", self.seller_1, self.loc_a, 500.0)
        with self.assertRaises(Exception):
            self.env["commission.settlement"].create_or_recalculate(self.period)

    def test_promotion_name_normalization_matches_sale_product_name(self):
        self._target(self.seller_1, amount=1000.0, rate=0.0)
        self._promotion("CERÁMICA CSL CUBIC GREY C1 (27*45) 1.70 M2", code="COD-CORTADO")
        self.env["commission.liquidation.rule"].create({
            "period_id": self.period.id,
            "seller_id": self.seller_1.id,
            "min_sales_amount": 200.0,
            "amount_per_m2": 0.5,
            "basis": "net",
        })
        self._sale(
            "GR-NAME-MATCH", self.seller_1, self.loc_a, 250.0,
            quantity=10.0, price_indicator=0.0,
            product_name="ceramica  csl cubic grey c1 27 45 1.70 m2",
        )
        settlement = self.env["commission.settlement"].create_or_recalculate(self.period)
        result = settlement.result_ids.filtered(lambda r: r.seller_id == self.seller_1)
        self.assertAlmostEqual(result.liquidation_sales, 250.0, places=4)
        self.assertAlmostEqual(result.liquidation_m2, 10.0, places=4)
        self.assertAlmostEqual(result.liquidation_bonus, 5.0, places=4)

    def test_duplicate_period_copies_liquidation_penalty_configuration(self):
        self.period.write({
            "liquidation_commission_rate_reduction": 0.4,
            "liquidation_penalty_exempt_seller_ids": [(6, 0, [self.seller_1.id])],
        })
        new_period = self.period.copy()
        self.assertAlmostEqual(
            new_period.liquidation_commission_rate_reduction, 0.4, places=4
        )
        self.assertIn(self.seller_1, new_period.liquidation_penalty_exempt_seller_ids)

    def test_liquidation_penalty_percent_must_be_valid(self):
        with self.assertRaises(Exception):
            self.period.liquidation_commission_rate_reduction = 120.0
    def test_sales_tiers_are_stepwise_not_proportional_32_34_40(self):
        """32k and 34k stay at 0.8%; only 40k moves to 1%."""
        scenarios = [
            ("GR-R32", 32000.0, 0.8, 256.0),
            ("GR-R34", 34000.0, 0.8, 272.0),
            ("GR-R39999", 39999.0, 0.8, 319.992),
            ("GR-R40", 40000.0, 1.0, 400.0),
        ]
        sellers = []
        for code, sales, expected_rate, expected_commission in scenarios:
            seller = self.Seller.create({
                "code": code,
                "name": code,
                "role": "seller",
            })
            sellers.append((seller, expected_rate, expected_commission))
            target = self.env["commission.seller.target"].create({
                "period_id": self.period.id,
                "seller_id": seller.id,
                "target_amount": 40000.0,
                "basis": "net",
            })
            self.env["commission.seller.target.tier"].create([
                {
                    "target_id": target.id,
                    "sales_threshold": 32000.0,
                    "commission_percent": 0.8,
                },
                {
                    "target_id": target.id,
                    "sales_threshold": 40000.0,
                    "commission_percent": 1.0,
                },
            ])
            self._sale(code + "-SALE", seller, self.loc_a, sales)

        settlement = self.env["commission.settlement"].create_or_recalculate(self.period)
        for seller, expected_rate, expected_commission in sellers:
            result = settlement.result_ids.filtered(lambda r: r.seller_id == seller)
            detail = result.detail_ids.filtered(lambda d: d.detail_type == "standard")
            self.assertAlmostEqual(detail.rate, expected_rate, places=4)
            self.assertAlmostEqual(
                result.standard_commission, expected_commission, places=3
            )

    def test_seller_target_forces_sales_tier_mode(self):
        target = self.env["commission.seller.target"].create({
            "period_id": self.period.id,
            "seller_id": self.seller_1.id,
            "target_amount": 40000.0,
            "basis": "net",
            "calculation_mode": "proportional",
        })
        self.assertEqual(target.calculation_mode, "sales_tier")
        target.write({"calculation_mode": "tier"})
        self.assertEqual(target.calculation_mode, "sales_tier")

