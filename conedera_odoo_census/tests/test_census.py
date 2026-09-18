import json

from odoo.exceptions import UserError, ValidationError
from odoo.tests.common import TransactionCase


class TestConederaCensus(TransactionCase):
    def setUp(self):
        super().setUp()
        self.business_type = self.env.ref("conedera_odoo_census.business_type_cellphones")
        self.partner = self.env["res.partner"].create(
            {
                "name": "Cliente GPS S.A.",
                "census_active": True,
                "customer_rank": 1,
                "vat": "0999999999001",
                "commercial_name": "Cliente GPS",
                "census_store_count": 2,
                "business_type_ids": [(6, 0, [self.business_type.id])],
                "customer_segment": "reseller",
                "capa": 5000.0,
                "owner_contact_name": "Ana Dueña",
                "owner_phone": "0990000001",
                "commercial_contact_name": "Carlos Compras",
                "phone": "042000001",
                "email": "compras@example.com",
                "street": "Av. Principal 123",
                "city": "Guayaquil",
            }
        )
        self.env["conedera.partner.opening.hour"].create(
            {
                "partner_id": self.partner.id,
                "day_of_week": "0",
                "opening_time": 9.0,
                "closing_time": 18.0,
            }
        )

    def test_multiple_business_types(self):
        accessories = self.env.ref("conedera_odoo_census.business_type_accessories")
        self.partner.write({"business_type_ids": [(4, accessories.id)]})
        self.assertEqual(len(self.partner.business_type_ids), 2)

    def test_structured_opening_hours(self):
        line = self.env["conedera.partner.opening.hour"].create(
            {
                "partner_id": self.partner.id,
                "day_of_week": "0",
                "opening_time": 9.0,
                "closing_time": 18.0,
            }
        )
        self.assertEqual(line.partner_id, self.partner)
        self.assertEqual(line.opening_time, 9.0)

    def test_visit_gps_distance(self):
        self.partner.write(
            {
                "census_gps_payload": json.dumps(
                    {"latitude": -2.170998, "longitude": -79.922359, "accuracy": 6.0}
                )
            }
        )
        payload = json.dumps(
            {"latitude": -2.171000, "longitude": -79.922360, "accuracy": 8.0}
        )
        visit = self.env["conedera.census.visit"].create(
            {
                "partner_id": self.partner.id,
                "gps_capture_payload": payload,
                "location_tolerance_m": 300,
            }
        )
        self.assertTrue(visit.gps_captured_at)
        self.assertEqual(visit.location_status, "in_range")
        self.assertLess(visit.distance_to_customer_m, 10)

    def test_quotation_context_links_visit(self):
        visit = self.env["conedera.census.visit"].create({"partner_id": self.partner.id})
        action = visit.action_create_quotation()
        self.assertEqual(action["context"]["default_partner_id"], self.partner.id)
        self.assertEqual(action["context"]["default_census_visit_id"], visit.id)

    def test_last_visit_metric_is_ui_compute(self):
        visit = self.env["conedera.census.visit"].create({"partner_id": self.partner.id})
        self.partner.invalidate_recordset(["census_last_visit_datetime"])
        self.assertEqual(self.partner.census_last_visit_datetime, visit.visit_datetime)

    def test_visit_quotation_marks_census_origin(self):
        visit = self.env["conedera.census.visit"].create({"partner_id": self.partner.id})
        order = self.env["sale.order"].create(
            {
                "partner_id": self.partner.id,
                "census_visit_id": visit.id,
            }
        )
        self.assertTrue(order.census_originated)
        self.assertEqual(order.census_visit_id, visit)

    def test_unique_census_per_vat(self):
        with self.assertRaises(ValidationError):
            self.env["res.partner"].create(
                {
                    "name": "Duplicado",
                    "census_active": True,
                    "vat": self.partner.vat,
                    "commercial_name": "Duplicado",
                }
            )

    def test_census_cannot_be_duplicated(self):
        with self.assertRaises(UserError):
            self.partner.copy()

    def test_store_count_is_editable_field(self):
        self.partner.write({"census_store_count": 4})
        self.assertEqual(self.partner.census_store_count, 4)

    def test_customer_history_contains_all_sale_orders(self):
        order = self.env["sale.order"].create({"partner_id": self.partner.id})
        self.assertIn(order, self.partner.census_sale_order_ids)

    def test_catastro_ready_without_gps(self):
        self.partner.invalidate_recordset(["census_ready_for_activity", "census_completion_state"])
        self.assertTrue(self.partner.census_ready_for_activity)
        self.assertEqual(self.partner.census_completion_state, "complete")
        self.assertFalse(self.partner.census_gps_captured_at)

    def test_incomplete_catastro_blocks_visit_and_quotation(self):
        self.partner.write({"census_store_count": 0})
        self.partner.invalidate_recordset(["census_ready_for_activity", "census_missing_requirements"])
        self.assertFalse(self.partner.census_ready_for_activity)
        with self.assertRaises(UserError):
            self.partner.action_new_census_visit()
        with self.assertRaises(UserError):
            self.partner.action_new_census_quotation()
        with self.assertRaises(UserError):
            self.env["conedera.census.visit"].create({"partner_id": self.partner.id})

    def test_visit_can_finish_without_gps(self):
        visit = self.env["conedera.census.visit"].create(
            {
                "partner_id": self.partner.id,
                "purchase_made": "no",
                "reschedule_visit": "no",
                "has_stock": "yes",
                "not_creditworthy": "no",
                "other_result": "no",
            }
        )
        visit.action_mark_done()
        self.assertEqual(visit.state, "done")
        self.assertEqual(visit.location_status, "no_visit_gps")
    def test_lookup_wizard_reuses_existing_partner(self):
        wizard = self.env["conedera.census.customer.lookup.wizard"].create(
            {"vat": self.partner.vat}
        )
        wizard.action_validate()
        self.assertEqual(wizard.validation_state, "found")
        self.assertEqual(wizard.existing_partner_id, self.partner)
        count_before = self.env["res.partner"].search_count([("vat", "=", self.partner.vat)])
        action = wizard.action_open_existing()
        count_after = self.env["res.partner"].search_count([("vat", "=", self.partner.vat)])
        self.assertEqual(count_before, count_after)
        self.assertEqual(action["res_id"], self.partner.id)

    def test_lookup_wizard_can_create_draft_from_name(self):
        wizard = self.env["conedera.census.customer.lookup.wizard"].create(
            {"customer_name": "Cliente Nuevo Sin RUC"}
        )
        wizard.action_validate()
        self.assertEqual(wizard.validation_state, "not_found")
        action = wizard.action_create_new()
        partner = self.env["res.partner"].browse(action["res_id"])
        self.assertTrue(partner.census_active)
        self.assertEqual(partner.name, "Cliente Nuevo Sin RUC")
        self.assertFalse(partner.census_ready_for_activity)

    def test_capa_is_required_for_activity(self):
        self.partner.write({"capa": 0})
        self.partner.invalidate_recordset(["census_ready_for_activity", "census_missing_requirements"])
        self.assertFalse(self.partner.census_ready_for_activity)
        self.assertIn("CAPA", self.partner.census_missing_requirements)
        with self.assertRaises(UserError):
            self.partner.action_new_census_visit()

    def test_mobile_brands_are_optional(self):
        brand = self.env.ref("conedera_odoo_census.mobile_brand_samsung")
        self.partner.write({"mobile_brand_ids": [(6, 0, [brand.id])]})
        self.partner.invalidate_recordset(["census_ready_for_activity"])
        self.assertTrue(self.partner.census_ready_for_activity)
        self.partner.write({"mobile_brand_ids": [(5, 0, 0)]})
        self.partner.invalidate_recordset(["census_ready_for_activity"])
        self.assertTrue(self.partner.census_ready_for_activity)


    def test_lookup_wizard_normalizes_vat_separators(self):
        self.partner.write({"vat": "09-99999999-001"})
        wizard = self.env["conedera.census.customer.lookup.wizard"].create(
            {"vat": "0999999999001"}
        )
        wizard.action_validate()
        self.assertEqual(wizard.validation_state, "found")
        self.assertEqual(wizard.existing_partner_id, self.partner)
        self.assertEqual(wizard.existing_name, self.partner.name)

    def test_timeline_contains_visit_and_quotation(self):
        visit = self.env["conedera.census.visit"].create({"partner_id": self.partner.id})
        order = self.env["sale.order"].create({"partner_id": self.partner.id})
        timeline = self.env["conedera.census.commercial.timeline"].search(
            [("partner_id", "=", self.partner.id)]
        )
        self.assertIn(visit, timeline.mapped("visit_id"))
        self.assertIn(order, timeline.mapped("sale_order_id"))

    def test_product_quote_summary_and_history(self):
        product = self.env["product.product"].create(
            {"name": "Equipo Demo", "list_price": 100.0}
        )
        order = self.env["sale.order"].create({"partner_id": self.partner.id})
        self.env["sale.order.line"].create(
            {
                "order_id": order.id,
                "product_id": product.id,
                "product_uom_qty": 3,
                "price_unit": 100.0,
                "discount": 10.0,
            }
        )
        summary = self.env["conedera.census.product.quote.summary"].search(
            [
                ("partner_id", "=", self.partner.id),
                ("product_id", "=", product.id),
            ],
            limit=1,
        )
        self.assertTrue(summary)
        self.assertEqual(summary.quoted_qty, 3)
        self.assertAlmostEqual(summary.avg_net_unit_price, 90.0, places=2)
        detail = self.env["conedera.census.product.quote.line"].search(
            [
                ("partner_id", "=", self.partner.id),
                ("product_id", "=", product.id),
            ],
            limit=1,
        )
        self.assertTrue(detail)
        self.assertAlmostEqual(detail.net_unit_price, 90.0, places=2)
