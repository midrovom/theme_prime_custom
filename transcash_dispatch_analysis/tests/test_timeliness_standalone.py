"""Completed timeliness, overdue backlog and exact scoped drilldowns."""
from copy import deepcopy
from datetime import date
import json
import unittest

import test_dashboard_standalone as dashboard_tests
from dispatch_queue_test.services.timeliness import dispatch_timeliness
from dispatch_queue_test.services.engine import evaluate, aggregate_invoice, invoice_key, unique_invoice_lines


def row(identity=1, completed="2026-01-04", **values):
    data = {"id": identity, "name": f"FA {identity}", "invoice_date": "2026-01-01",
        "completion_date": completed, "cutoff_date": "2026-01-15", "city": "GUAYAQUIL", "customer": "Cliente",
        "delivery": "Entrega Transcash", "physically_completed": bool(completed), "pending": not bool(completed),
        "quality_issue": False, "has_adjustment": False}
    data.update(values)
    pack = {"rules": [{"city_key": "", "delivery_key": "", "max_days": 3, "day_type": "calendar"}]}
    return evaluate(data, pack)


class TimelinessTests(unittest.TestCase):
    def test_pie_uses_only_complete_evaluable_invoices_not_all_due_invoices(self):
        result = dispatch_timeliness([row(1), row(2, "2026-01-06"), row(3, None)], True)
        self.assertEqual(result["pie"]["total"], 2)
        self.assertEqual([part["pct"] for part in result["pie"]["series"]], [50, 50])
        self.assertEqual(result["pie"]["pending_total"], 1)
        self.assertEqual(result["delays"]["pending"]["max_days"], 11)
        self.assertEqual(result["detail_ids"], {"timely_completed": [1], "late_completed": [2], "overdue_pending": [3]})

    def test_completion_on_deadline_is_timely(self):
        self.assertEqual(dispatch_timeliness([row()])["pie"]["series"][0]["pct"], 100)

    def test_completion_before_deadline_is_timely_with_no_negative_delay(self):
        result = dispatch_timeliness([row(completed="2026-01-01")])
        self.assertEqual(result["pie"]["series"][0]["value"], 1)
        self.assertIsNone(result["delays"]["completed"]["max_days"])

    def test_late_average_excludes_on_time_and_pending_invoices(self):
        result = dispatch_timeliness([row(1), row(2, "2026-01-06"), row(3, "2026-01-10"), row(4, None)])
        completed = result["delays"]["completed"]
        self.assertEqual((completed["count"], completed["avg_days"], completed["max_days"]), (2, 4, 6))
        self.assertEqual([item["id"] for item in completed["top"]], [3, 2])

    def test_pending_as_of_snapshot_not_today_or_last_partial_dispatch(self):
        pending = row(1, None, cutoff_date="2026-01-07", completion_date=False, last_dispatch_date="2026-01-02")
        result = dispatch_timeliness([pending])
        self.assertEqual(result["delays"]["pending"]["top"][0]["reference_date"], "2026-01-07")
        self.assertEqual(result["delays"]["pending"]["max_days"], 3)
        self.assertFalse(result["pie"]["available"])

    def test_due_today_and_open_pending_are_not_overdue(self):
        result = dispatch_timeliness([row(1, None, cutoff_date="2026-01-04"), row(2, None, cutoff_date="2026-01-03")])
        self.assertEqual(result["delays"]["pending"]["count"], 0)
        self.assertEqual(result["pie"]["pending_total"], 2)

    def test_unmeasured_closed_and_pending_do_not_become_zero_percent(self):
        result = dispatch_timeliness([row(1, quality_issue=True), row(2, None, has_adjustment=True)])
        self.assertFalse(result["pie"]["available"])
        self.assertEqual(result["pie"]["excluded_completed"], 1)
        self.assertTrue(all(part["pct"] is None for part in result["pie"]["series"]))

    def test_no_rule_adjusted_invalid_and_inconsistent_dates_are_excluded(self):
        for values in ({"sla_configured": False}, {"eligible": False}, {"has_adjustment": True},
                       {"quality_issue": True}, {"completion_date": False}, {"deadline": False},
                       {"completion_date": "bad-date"}, {"completion_date": "2026-01-20"},
                       {"completion_date": "2025-12-31"}, {"deadline": "2025-12-31"}):
            candidate = {**row(), **values}
            with self.subTest(values=values):
                result = dispatch_timeliness([candidate])
                self.assertFalse(result["pie"]["available"])
                self.assertEqual(result["pie"]["excluded_completed"], 1)

    def test_contradictory_status_dates_and_completion_flags_are_excluded(self):
        for candidate in ({**row(), "sla_status": "late"}, {**row(1, "2026-01-06"), "sla_status": "on_time"},
                          {**row(), "pending": True}):
            self.assertFalse(dispatch_timeliness([candidate])["pie"]["available"])

    def test_business_deadline_keeps_holidays_but_delay_is_calendar_days(self):
        candidate = {**row(1, "2026-01-12"), "invoice_date": "2026-01-02"}
        pack = {"holidays": ["2026-01-05"], "rules": [{"max_days": 1, "day_type": "business"}]}
        candidate = evaluate(candidate, pack)
        self.assertEqual(candidate["deadline"], "2026-01-06")
        self.assertEqual(candidate["late_days"], 4)  # Existing SLA unit stays unchanged.
        result = dispatch_timeliness([candidate])
        self.assertEqual(result["delays"]["completed"]["max_days"], 6)
        self.assertEqual(result["day_unit"], "calendar")

    def test_top_ten_is_ordered_but_average_covers_all_late_invoices(self):
        rows = [row(i, date(2026, 1, 4+i).isoformat(), cutoff_date="2026-02-01") for i in range(1, 21)]
        summary = dispatch_timeliness(reversed(rows))["delays"]["completed"]
        self.assertEqual(summary["count"], 20)
        self.assertEqual(summary["avg_days"], 10.5)
        self.assertEqual([item["delay_days"] for item in summary["top"]], list(range(20, 10, -1)))

    def test_ties_are_stable_when_source_order_changes(self):
        rows = [row(2, "2026-01-07"), row(1, "2026-01-07")]
        self.assertEqual(dispatch_timeliness(rows), dispatch_timeliness(reversed(rows)))

    def test_no_ids_in_normal_rpc_and_input_remains_unchanged(self):
        rows = [row(1), row(2, "2026-01-07")]
        before = deepcopy(rows)
        result = dispatch_timeliness(rows)
        self.assertNotIn("detail_ids", result)
        self.assertEqual(rows, before)
        json.dumps(result, allow_nan=False)

    def test_empty_has_no_fabricated_percentages_or_zero_delay(self):
        result = dispatch_timeliness([])
        self.assertEqual(result["pie"]["total"], 0)
        self.assertIsNone(result["pie"]["series"][0]["pct"])
        self.assertIsNone(result["delays"]["completed"]["avg_days"])

    def test_repeated_detail_is_unique_and_distinct_skus_form_one_invoice(self):
        raw = {"TipoFactura": "FA", "NumeroFactura": "001", "Ciudad": "Guayaquil", "Cond_Entrega": "Entrega Transcash",
            "FechaFactura": "2026-01-01", "CodBodega": "A", "CodProducto": "SKU1", "Facturado": 1,
            "DespachoFisico": 1, "Pendiente": 0, "UltimoDespacho": "2026-01-07"}
        details, removed, _ = unique_invoice_lines([raw, raw, {**raw, "CodProducto": "SKU2"}])
        candidate = evaluate(aggregate_invoice(invoice_key(raw), details, "2026-01-15"),
            {"rules": [{"max_days": 3, "day_type": "calendar"}]})
        result = dispatch_timeliness([{**candidate, "id": 1}])
        self.assertEqual(removed, 1)
        self.assertEqual(result["pie"]["total"], 1)
        self.assertEqual(result["delays"]["completed"]["count"], 1)


class DashboardTimelinessTests(unittest.TestCase):
    setUp = dashboard_tests.DashboardTests.setUp

    def test_invoice_period_and_current_company_scope_apply_to_new_indicators(self):
        self.assertEqual(self.service.get_data()["timeliness"]["pie"]["total"], 1)
        result = self.service.get_data({"date_from": "2026-02-01"})
        self.assertEqual(result["timeliness"]["pie"]["total"], 0)
        self.assertEqual(result["timeliness"]["delays"]["pending"]["count"], 1)
        self.rows.append({**self.rows[0], "id": 99, "company_id": [2, "Other"]})
        self.rows.append({**self.rows[0], "id": 100, "is_current": False})
        self.assertEqual(self.service.get_data()["timeliness"]["pie"]["total"], 1)

    def test_detail_actions_match_measured_cohorts_and_keep_explicit_views(self):
        for category, expected in (("timely_completed", [1]), ("late_completed", []), ("overdue_pending", [2])):
            action = self.service.get_detail_action({}, category)
            self.assertIn(("id", "in", expected), action["domain"])
            self.assertIn(("is_current", "=", True), action["domain"])
            self.assertEqual(action["views"][0], (False, "list"))
        action = self.service.get_detail_action({"date_from": "2026-02-02"}, "overdue_pending")
        self.assertIn(("invoice_date", ">=", "2026-02-02"), action["domain"])
        self.assertIn(("id", "in", []), action["domain"])

    def test_multiwarehouse_scope_recalculates_completion_once_per_invoice(self):
        from types import SimpleNamespace
        raw = {"TipoFactura": "FA", "NumeroFactura": "2", "Ciudad": "GUAYAQUIL", "Cond_Entrega": "Entrega Transcash",
            "FechaFactura": "2026-02-01", "Facturado": 1, "DespachoFisico": 1, "Pendiente": 0,
            "UltimoDespacho": "2026-02-05", "CodProducto": "A"}
        self.rows[:] = [{**self.rows[1], "warehouse_ids": [10, 20], "snapshot_id": [1, "Cut"], "invoice_key": invoice_key(raw)}]
        self.lines[:] = [{"id": index, "invoice_id": [2, "FA 2"], "warehouse_id": [warehouse, "W"],
            "pending_qty": 1 if warehouse == 20 else 0, "pending_weight": 9000 if warehouse == 20 else 0,
            "raw_data": {**raw, "CodBodega": str(warehouse),
                **({"DespachoFisico": 0, "Pendiente": 1, "UltimoDespacho": False} if warehouse == 20 else {})}}
            for index, warehouse in enumerate((10, 20), 1)]
        snapshot = SimpleNamespace(id=1, policy_pack={"rules": [{"max_days": 3, "day_type": "calendar"}]})
        self.service.env.models["dispatch.snapshot"].browse = lambda ids: [snapshot]
        completed = self.service.get_data({"warehouse_ids": [10]})
        self.assertEqual(completed["timeliness"]["pie"]["total"], 1)
        self.assertEqual(completed["timeliness"]["delays"]["completed"]["max_days"], 1)
        both = self.service.get_data({"warehouse_ids": [10, 20]})
        self.assertEqual(both["timeliness"]["pie"]["total"], 0)
        self.assertEqual(both["timeliness"]["delays"]["pending"]["count"], 1)
        self.assertIn(("id", "in", [2]), self.service.get_detail_action({"warehouse_ids": [10]}, "late_completed")["domain"])
        self.assertIn(("id", "in", []), self.service.get_detail_action({"warehouse_ids": [10, 20]}, "late_completed")["domain"])


if __name__ == "__main__":
    unittest.main()
