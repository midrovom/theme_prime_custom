import json

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
                "store_count": 2,
                "business_type_ids": [(6, 0, [self.business_type.id])],
                "customer_segment": "reseller",
                "census_gps_payload": json.dumps(
                    {"latitude": -2.170998, "longitude": -79.922359, "accuracy": 6.0}
                ),
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
