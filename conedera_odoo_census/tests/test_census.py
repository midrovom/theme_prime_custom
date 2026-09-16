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
