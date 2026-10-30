"""Regressions for the reported action error, pallets and the 27.95 t example."""
from datetime import date, timedelta
from unittest.mock import patch
import unittest

import test_dashboard_standalone as dashboard_tests
from test_planning_standalone import planning, invoice, line, pack
from test_engine_standalone import e, line as source_line, inv

module = dashboard_tests.module


class SimplerPlanningTests(unittest.TestCase):
    def vehicles(self):
        return [{"id": i, "name": name, "capacity_tons": tons, "utilization_pct": 90}
                for i, (_, name, tons) in enumerate(planning.DEFAULT_VEHICLES, 1)]

    def backlog(self):
        return [line(pending_weight=24000), line(warehouse_code="B", warehouse="B", pending_weight=3500),
                line(warehouse_code="C", warehouse="C", pending_weight=450)]

    def test_reported_27_95_t_separate_and_grouped_are_distinct_scenarios(self):
        packs = pack(vehicles=self.vehicles())
        separate = planning.build_transport_plan([invoice()], self.backlog(), packs)
        grouped = planning.build_transport_plan([invoice()], self.backlog(), packs, grouping="destination")
        self.assertEqual(separate["required_vehicles"], 3)
        self.assertEqual(separate["destinations"][0]["origin_count"], 3)
        self.assertEqual(separate["destinations"][0]["invoice_count"], 1)
        self.assertEqual(grouped["pending_tons"], 27.95)
        self.assertEqual(grouped["required_vehicles"], 1)
        self.assertEqual(grouped["trips"], 2)
        self.assertEqual(grouped["days_required_fleet"], 2)
        self.assertEqual(grouped["lanes"][0]["estimate"]["capacity_tons"], 28)
        self.assertEqual(grouped["lanes"][0]["estimate"]["useful_tons"], 25.2)
        self.assertEqual(len(grouped["lanes"][0]["origins"]), 3)
        self.assertEqual(grouped["pending_invoices"], 1)

    def test_one_day_requires_two_grouped_trailers_not_one_overloaded_trip(self):
        packs = pack(vehicles=self.vehicles(), settings={"target_days": 1, "available_vehicles": 0, "trips_per_day": 1})
        grouped = planning.build_transport_plan([invoice()], self.backlog(), packs, grouping="destination")
        self.assertEqual(grouped["required_vehicles"], 2)
        self.assertEqual(grouped["additional_vehicles"], 2)
        self.assertEqual(grouped["days_required_fleet"], 1)
        self.assertIsNone(grouped["days_current_fleet"])

    def test_grouping_preserves_origin_specific_restrictions(self):
        packs = pack(vehicles=self.vehicles(), routes=[{"city": "Guayaquil", "warehouse_code": "B", "vehicle_id": 1}])
        grouped = planning.build_transport_plan([invoice()], self.backlog(), packs, grouping="destination")
        self.assertEqual(len(grouped["lanes"]), 3)
        self.assertTrue(all(lane["grouping_note"] for lane in grouped["lanes"]))
        self.assertEqual(next(r for r in grouped["lanes"] if r["warehouse_code"] == "B")["estimate"]["capacity_tons"], 3.5)

    def test_grouping_does_not_erase_unknown_weight_or_review_notes(self):
        rows = [*self.backlog(), line(warehouse_code="D", pending_weight=0)]
        grouped = planning.build_transport_plan([invoice(quality_issue=True)], rows, pack(vehicles=self.vehicles()), grouping="destination")
        self.assertEqual(grouped["pending_tons"], 27.95)
        self.assertFalse(grouped["complete"])
        self.assertEqual(grouped["unknown_weight_lines"], 1)
        self.assertTrue(grouped["destinations"][0]["issues"])

    def test_recommended_fleet_days_are_not_current_fleet_days(self):
        result = planning.vehicle_estimate(54000, pack()[1]["vehicles"][0],
            {"target_days": 3, "available_vehicles": 1, "trips_per_day": 1})
        self.assertEqual((result["days_current_fleet"], result["days_required_fleet"]), (6, 3))

    def test_destination_grouping_keeps_companies_and_sources_separate(self):
        invoices = [invoice(), invoice(2, source_id=[2, "Other"]), invoice(3, company_id=[2, "Other"])]
        result = planning.build_transport_plan(invoices, [line(), line(2), line(3)], {**pack(), 2:pack()[1]}, grouping="destination")
        self.assertEqual(len(result["lanes"]), 3)


class PalletTests(unittest.TestCase):
    def test_missing_billed_pallets_are_unknown_not_a_zero_measurement(self):
        result = e.pallet_metrics(source_line(PalletsPendientes=2.5))
        self.assertFalse(result["invoiced_pallets_available"])
        self.assertEqual(result["invoiced_pallets_missing_rows"], 1)
        self.assertTrue(result["pending_pallets_available"])
        self.assertEqual(result["pending_pallets"], 2.5)

    def test_reported_zero_billed_pallets_remain_known(self):
        self.assertTrue(e.pallet_metrics(source_line(PalletsFacturados=0))["invoiced_pallets_available"])

    def test_no_ratio_is_inferred_for_heterogeneous_warehouse_rows(self):
        result = inv([source_line(Facturado=100, DespachoFisico=50, Pendiente=50, PalletsPendientes=2)])
        self.assertEqual(result["invoiced_pallets_missing_rows"], 1)
        self.assertEqual(result["invoiced_pallets"], 0)

    def test_reported_pallets_are_summed_once_per_unique_detail(self):
        raw = source_line(PalletsFacturados=10.25, PalletsPendientes=3.75)
        unique, _, _ = e.unique_invoice_lines([raw, raw])
        stats = e.summarize([inv(unique)])
        self.assertEqual((stats["invoiced_pallets"], stats["pending_pallets"]), (10.25, 3.75))

    def test_unknown_pallets_do_not_become_zero_on_charts(self):
        rows = [inv([source_line()])]
        self.assertIsNone(e.metric_value(rows, "invoiced_pallets"))
        self.assertIsNone(e.metric_value(rows, "pending_pallets"))

    def test_negative_values_are_marked_unavailable(self):
        result = e.pallet_metrics(source_line(PalletsFacturados=-1, PalletsPendientes=-1))
        self.assertFalse(result["invoiced_pallets_available"])
        self.assertFalse(result["pending_pallets_available"])

    def test_empty_pending_quantity_needs_no_pending_pallets(self):
        result = e.pallet_metrics(source_line(Pendiente=0, DespachoFisico=10))
        self.assertTrue(result["pending_pallets_available"])
        self.assertEqual(result["pending_pallets"], 0)


class DashboardRegressionTests(unittest.TestCase):
    setUp = dashboard_tests.DashboardTests.setUp
    def test_all_kpi_actions_have_views_and_retain_loaded_date_domain(self):
        filters = {"date_from": "2026-02-01", "date_to": "2026-02-02"}
        for category in ("all", "pending", "overdue", "quality", "lead", "mature", "no_rule"):
            action = self.service.get_detail_action(filters, category)
            self.assertEqual(action["views"], [(False, mode) for mode in ("list", "form", "pivot", "graph")])
            self.assertIn(("invoice_date", ">=", filters["date_from"]), action["domain"])
            self.assertIn(("is_current", "=", True), action["domain"])

    def test_default_dates_are_thirty_inclusive_days_in_user_context(self):
        for today in (date(2026, 10, 29), date(2026, 1, 1), date(2024, 3, 1)):
            with patch.object(module.fields.Date, "context_today", return_value=today):
                filters = self.service.get_default_filters()
            self.assertEqual(filters["date_to"], today.isoformat())
            self.assertEqual(filters["date_from"], (today - timedelta(days=29)).isoformat())

    def test_invalid_grouping_is_rejected(self):
        with self.assertRaises(module.ValidationError):
            self.service.get_data({"planning_grouping": "unknown"})

    def test_history_action_has_explicit_views(self):
        from test_import_queue_standalone import Job, Snapshot
        job = Job()
        job.name = "History"
        action = Snapshot.action_open_invoices(job)
        self.assertEqual(action["views"][0], (False, "list"))


if __name__ == "__main__":
    unittest.main()
