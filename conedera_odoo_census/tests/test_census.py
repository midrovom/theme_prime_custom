import json

from odoo.tests.common import TransactionCase


class TestConederaCensus(TransactionCase):
    def setUp(self):
        super().setUp()
        self.partner = self.env["res.partner"].create(
            {
                "name": "Cliente GPS",
                "census_active": True,
                "customer_rank": 1,
                "vat": "0999999999001",
                "commercial_name": "Cliente GPS",
                "business_type": "cellphones",
                "customer_census_type": "reseller",
                "partner_latitude": -2.170998,
                "partner_longitude": -79.922359,
            }
        )

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

    def test_last_visit_is_stored_and_sortable(self):
        visit = self.env["conedera.census.visit"].create({"partner_id": self.partner.id})
        self.partner.invalidate_recordset(["census_last_visit_datetime"])
        self.assertEqual(self.partner.census_last_visit_datetime, visit.visit_datetime)
        found = self.env["res.partner"].search(
            [("id", "=", self.partner.id)], order="census_last_visit_datetime desc"
        )
        self.assertEqual(found, self.partner)

    def test_visit_quotation_marks_census_origin(self):
        visit = self.env["conedera.census.visit"].create({"partner_id": self.partner.id})
        order = self.env["sale.order"].create({
            "partner_id": self.partner.id,
            "census_visit_id": visit.id,
        })
        self.assertTrue(order.census_originated)
        self.assertEqual(order.census_visit_id, visit)
