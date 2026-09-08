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

    def _sale(self, code, seller, location, net):
        return self.Sale.create({
            "fingerprint": code,
            "registration_date": "2026-05-10",
            "seller_id": seller.id,
            "location_id": location.id,
            "document_type": "FA",
            "number": code,
            "invoice": code,
            "product_code": code,
            "quantity": 1.0,
            "total_price": net,
            "total_net": net,
            "profit": net * 0.30,
            "document_sign": 1.0,
        })

    def _location_target(self, amount=1000.0):
        return self.env["commission.location.target"].create({
            "period_id": self.period.id,
            "location_id": self.loc_a.id,
            "target_amount": amount,
            "basis": "net",
            "required_achievement": 100.0,
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

    def test_manager_fixed_minimum_is_independent_from_seller_target(self):
        # El administrador necesita meta para aparecer como resultado de liquidación.
        self._target(self.manager, amount=100.0, rate=0.0)
        self._target(self.seller_1, amount=1000.0, rate=0.0)
        self._location_target(amount=500.0)
        self.env["commission.manager.seller.rule"].create({
            "period_id": self.period.id,
            "manager_id": self.manager.id,
            "seller_id": self.seller_1.id,
            "location_id": self.loc_a.id,
            "minimum_type": "fixed",
            "minimum_amount": 600.0,
            "commission_percent": 1.0,
            "basis": "net",
        })

        # Solo llega a 70% de su meta propia, pero supera el mínimo ADMIN de 600.
        # 500 en local A habilita la meta local; 200 en B también cuenta para el mínimo.
        self._sale("GR-F1A", self.seller_1, self.loc_a, 500.0)
        self._sale("GR-F1B", self.seller_1, self.loc_b, 200.0)

        settlement = self.env["commission.settlement"].create_or_recalculate(self.period)
        manager_result = settlement.result_ids.filtered(lambda r: r.seller_id == self.manager)
        self.assertAlmostEqual(manager_result.management_commission, 7.0, places=4)

    def test_manager_minimum_can_be_percent_of_seller_target(self):
        self._target(self.manager, amount=100.0, rate=0.0)
        self._target(self.seller_1, amount=1000.0, rate=0.0)
        self._location_target(amount=600.0)
        rule = self.env["commission.manager.seller.rule"].create({
            "period_id": self.period.id,
            "manager_id": self.manager.id,
            "seller_id": self.seller_1.id,
            "location_id": self.loc_a.id,
            "minimum_type": "target_percent",
            "minimum_target_percent": 80.0,
            "commission_percent": 1.5,
            "basis": "net",
        })
        self.assertAlmostEqual(rule.effective_minimum, 800.0, places=4)

        self._sale("GR-P1A", self.seller_1, self.loc_a, 600.0)
        self._sale("GR-P1B", self.seller_1, self.loc_b, 250.0)

        settlement = self.env["commission.settlement"].create_or_recalculate(self.period)
        manager_result = settlement.result_ids.filtered(lambda r: r.seller_id == self.manager)
        # 850 >= 800 y el local A alcanzó 600/600. Comisión 850 * 1.5%.
        self.assertAlmostEqual(manager_result.management_commission, 12.75, places=4)

    def test_manager_commission_requires_location_target(self):
        self._target(self.manager, amount=100.0, rate=0.0)
        self._target(self.seller_1, amount=1000.0, rate=0.0)
        self._location_target(amount=1000.0)
        self.env["commission.manager.seller.rule"].create({
            "period_id": self.period.id,
            "manager_id": self.manager.id,
            "seller_id": self.seller_1.id,
            "location_id": self.loc_a.id,
            "minimum_type": "fixed",
            "minimum_amount": 500.0,
            "commission_percent": 1.0,
            "basis": "net",
        })
        self._sale("GR-L1A", self.seller_1, self.loc_a, 400.0)
        self._sale("GR-L1B", self.seller_1, self.loc_b, 400.0)

        settlement = self.env["commission.settlement"].create_or_recalculate(self.period)
        manager_result = settlement.result_ids.filtered(lambda r: r.seller_id == self.manager)
        # El vendedor supera 500, pero el local A solo llega a 40% de su meta.
        self.assertAlmostEqual(manager_result.management_commission, 0.0, places=4)

    def test_reports_are_available(self):
        self._target(self.seller_1)
        settlement = self.env["commission.settlement"].create_or_recalculate(self.period)
        result = settlement.result_ids.filtered(lambda r: r.seller_id == self.seller_1)
        self.assertEqual(settlement.action_print_settlement()["type"], "ir.actions.report")
        self.assertEqual(result.action_print_individual()["type"], "ir.actions.report")
