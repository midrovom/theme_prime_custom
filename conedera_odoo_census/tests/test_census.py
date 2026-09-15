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
