from odoo.tests.common import TransactionCase


class TestCommissionCalculation(TransactionCase):
    def setUp(self):
        super().setUp()
        self.Location = self.env["commission.location"]
        self.Seller = self.env["commission.seller"]
        self.Sale = self.env["commission.sale"]
        self.Period = self.env["commission.period"]

        self.location = self.Location.create({"code": "SDO", "name": "Santo Domingo"})
        self.manager = self.Seller.create({"code": "ADM1", "name": "Administrador", "role": "manager"})
        self.seller = self.Seller.create({
            "code": "181", "name": "Vanessa Siguenza", "role": "seller",
            "manager_id": self.manager.id, "default_location_id": self.location.id,
        })
        self.project = self.Seller.create({"code": "PROY1", "name": "Proyectos", "role": "project"})
        self.period = self.Period.create({
            "name": "Febrero 2026",
            "date_start": "2026-02-01",
            "date_end": "2026-02-28",
        })

    def _sale(self, fp, seller, net, *, indicator=0.0, quantity=10.0, origin="Importado"):
        return self.Sale.create({
            "fingerprint": fp,
            "registration_date": "2026-02-10",
            "seller_id": seller.id,
            "location_id": self.location.id,
            "document_type": "FA",
            "number": fp,
            "invoice": fp,
            "product_code": "P-" + fp,
            "origin": origin,
            "quantity": quantity,
            "cost": 10.0,
            "total_cost": 100.0,
            "total_price": net,
            "total_net": net,
            "profit": net * 0.3,
            "price_indicator": indicator,
            "document_sign": 1.0,
        })

    def test_create_sale_generates_missing_masters(self):
        sale = self.Sale.create({
            "registration_date": "2026-02-15",
            "document_type": "FA",
            "number": "AUTO-1",
            "seller_code": "NEW001",
            "seller_name": "VENDEDOR NUEVO   ",
            "location_code": "UIO",
            "location_name": "001 Quito Matriz   ",
            "product_code": "P1",
            "quantity": 12.5,
            "total_net": 100.0,
        })
        self.assertTrue(sale.seller_id)
        self.assertTrue(sale.location_id)
        self.assertEqual(sale.seller_id.code, "NEW001")
        self.assertEqual(sale.seller_id.name, "VENDEDOR NUEVO")
        self.assertTrue(sale.seller_id.created_from_sales)
        self.assertEqual(sale.location_id.code, "UIO")
        self.assertEqual(sale.location_id.name, "001 Quito Matriz")
        self.assertTrue(sale.location_id.created_from_sales)
        self.assertEqual(sale.seller_id.default_location_id, sale.location_id)

    def test_combined_rules(self):
        seller_target = self.env["commission.seller.target"].create({
            "period_id": self.period.id,
            "seller_id": self.seller.id,
            "target_amount": 1000.0,
            "basis": "net",
        })
        self.env["commission.seller.target.tier"].create([
            {"target_id": seller_target.id, "min_achievement": 80.0, "max_achievement": 99.9999, "commission_percent": 1.0},
            {"target_id": seller_target.id, "min_achievement": 100.0, "commission_percent": 2.0},
        ])

        admin_target = self.env["commission.seller.target"].create({
            "period_id": self.period.id,
            "seller_id": self.manager.id,
            "target_amount": 500.0,
            "basis": "net",
        })
        self.env["commission.seller.target.tier"].create([
            {"target_id": admin_target.id, "min_achievement": 80.0, "max_achievement": 99.9999, "commission_percent": 1.5},
            {"target_id": admin_target.id, "min_achievement": 100.0, "commission_percent": 2.5},
        ])

        self.env["commission.location.target"].create({
            "period_id": self.period.id,
            "location_id": self.location.id,
            "target_amount": 1000.0,
            "basis": "net",
            "required_achievement": 100.0,
        })
        self.env["commission.manager.rule"].create({
            "period_id": self.period.id,
            "manager_id": self.manager.id,
            "location_id": self.location.id,
            "min_seller_sales": 500.0,
            "commission_percent": 0.5,
            "basis": "net",
            "require_location_target": True,
        })
        self.env["commission.project.rule"].create({
            "period_id": self.period.id,
            "seller_id": self.project.id,
            "origin": "Importado",
            "commission_percent": 3.0,
            "basis": "net",
        })
        self.env["commission.liquidation.rule"].create({
            "period_id": self.period.id,
            "seller_id": self.seller.id,
            "indicator_value": 3.0,
            "min_sales_amount": 500.0,
            "amount_per_m2": 0.20,
            "basis": "net",
        })

        self._sale("S1", self.seller, 900.0, indicator=3.0, quantity=10.0)
        self._sale("A1", self.manager, 500.0, quantity=2.0)
        self._sale("P1", self.project, 1000.0, origin="Importado", quantity=3.0)

        settlement = self.env["commission.settlement"].create_or_recalculate(self.period)
        seller_result = settlement.result_ids.filtered(lambda r: r.seller_id == self.seller)
        manager_result = settlement.result_ids.filtered(lambda r: r.seller_id == self.manager)
        project_result = settlement.result_ids.filtered(lambda r: r.seller_id == self.project)

        self.assertAlmostEqual(seller_result.standard_commission, 9.0, places=4)
        self.assertAlmostEqual(seller_result.liquidation_bonus, 2.0, places=4)
        self.assertAlmostEqual(seller_result.total_commission, 11.0, places=4)

        self.assertAlmostEqual(manager_result.standard_commission, 12.5, places=4)
        self.assertAlmostEqual(manager_result.management_commission, 4.5, places=4)
        self.assertAlmostEqual(manager_result.total_commission, 17.0, places=4)

        self.assertAlmostEqual(project_result.project_commission, 30.0, places=4)

    def test_below_80_percent_pays_zero(self):
        target = self.env["commission.seller.target"].create({
            "period_id": self.period.id,
            "seller_id": self.seller.id,
            "target_amount": 1000.0,
        })
        self.env["commission.seller.target.tier"].create({
            "target_id": target.id,
            "min_achievement": 80.0,
            "commission_percent": 1.0,
        })
        self._sale("S2", self.seller, 799.99)
        settlement = self.env["commission.settlement"].create_or_recalculate(self.period)
        result = settlement.result_ids.filtered(lambda r: r.seller_id == self.seller)
        self.assertAlmostEqual(result.standard_commission, 0.0, places=4)

    def test_api_row_uses_quantity_and_creates_masters(self):
        row = [
            "FA", "301950", "19155", "2026.02.02", "2026.02.03",
            "ANDRADE ALAVA VERONICA YASMIN", "VANESSA SIGUENZA   ", "999", "ANT",
            "CERAMICA", "SAN LORENZO", "0020060008C1",
            "CERAMICA CSL CUBIC GREY C1 (27*45)", 1.70, 4.646, 7.9, 17.53,
            30, 0, 12.2719, 3, 5.26, 4.37, 0, "", "CERAMICA SAN LORENZO S.A.C",
            "Importado", "SDX", "010-001 Santo Domingo F/E",
        ]
        result = self.Sale.import_rows([row])
        self.assertEqual(result["created"], 1)
        sale = self.Sale.search([("number", "=", "301950")], limit=1)
        self.assertAlmostEqual(sale.quantity, 1.70, places=4)
        self.assertEqual(sale.seller_name, "VANESSA SIGUENZA")
        self.assertEqual(sale.location_code, "SDX")
        self.assertEqual(sale.seller_id.code, "999")
        self.assertEqual(sale.location_id.code, "SDX")
