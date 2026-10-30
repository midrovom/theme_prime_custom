"""Agreement cohorts, due dates and non-overlapping billed/pending pies."""
import unittest

from test_planning_standalone import load
import test_dashboard_standalone as dashboard_tests

overview = load("overview")


def row(ident=1, **changes):
    return {"id": ident, "pending": True, "pending_weight": 2000, "invoiced_weight": 10000,
        "dispatched_weight": 8000, "invoiced_weight_missing_rows": 0, "dispatched_weight_missing_rows": 0,
        "sla_configured": True, "sla_days": 3, "sla_day_type": "calendar", "eligible": True,
        "sla_status": "open", "deadline": "2026-10-31", "cutoff_date": "2026-10-29", "city": "GUAYAQUIL",
        "delivery": "Entrega Transcash", "quality_issue": False, "has_adjustment": False, **changes}


class OverviewTests(unittest.TestCase):
    def test_three_and_nine_day_agreements_are_actual_configured_terms(self):
        rows = [row(), row(2, sla_days=9, pending_weight=4000, sla_status="overdue")]
        result = overview.pending_by_agreement(rows)
        self.assertEqual([g["key"] for g in result["groups"]], ["calendar:3", "calendar:9"])
        self.assertEqual([g["pending_tons"] for g in result["groups"]], [2, 4])
        self.assertEqual(result["groups"][1]["overdue"], 1)

    def test_business_and_calendar_agreements_remain_distinct(self):
        result = overview.pending_by_agreement([row(), row(2, sla_day_type="business")])
        self.assertEqual(len(result["groups"]), 2)
        self.assertEqual({g["label"] for g in result["groups"]}, {"3 días calendario", "3 días hábiles"})

    def test_pending_partial_and_quality_rows_are_not_lost(self):
        rows = [row(), row(2, eligible=False, sla_status="adjusted"), row(3, pending=False),
                row(4, sla_configured=False, eligible=False, sla_status="no_rule")]
        result = overview.pending_by_agreement(rows)
        self.assertEqual(result["pending"], 3)
        self.assertEqual(sum(g["within"] + g["overdue"] + g["review"] for g in result["groups"]), 3)
        self.assertEqual(result["due"]["review"], 2)
        self.assertEqual(result["groups"][-1]["key"], "no_rule")

    def test_upcoming_days_use_each_cutoff_not_today_or_agreement_length(self):
        rows = [row(1, deadline="2026-10-29", sla_status="due_today"), row(2, deadline="2026-10-30"),
                row(3, deadline="2026-11-01", sla_days=9), row(4, deadline="2026-11-02"),
                row(5, deadline="2026-10-28", sla_status="overdue")]
        due = overview.pending_by_agreement(rows)["due"]
        self.assertEqual(due, {"overdue": 1, "due_today": 1, "next_3_days": 2, "later": 1, "review": 0})

    def test_zero_day_agreement_is_configured_and_not_no_rule(self):
        group = overview.pending_by_agreement([row(sla_days=0)])["groups"][0]
        self.assertEqual(group["key"], "calendar:0")

    def test_ids_are_opt_in_for_precise_filtered_drilldowns(self):
        plain = overview.pending_by_agreement([row()])
        detailed = overview.pending_by_agreement([row()], True)
        self.assertNotIn("invoice_ids", plain["groups"][0])
        self.assertEqual(detailed["groups"][0]["invoice_ids"], [1])

    def test_invoice_pie_counts_pending_as_subset_of_all_invoices(self):
        chart = overview.dispatch_progress([row(), row(2, pending=False), row(3, pending=False, has_adjustment=True)])["invoices"]
        self.assertEqual(chart["total"], 3)
        self.assertEqual([p["value"] for p in chart["series"]], [2, 1])
        self.assertAlmostEqual(sum(p["pct"] for p in chart["series"]), 100)
        self.assertEqual(chart["series"][0]["label"], "Sin pendiente")

    def test_weight_pie_uses_billed_as_denominator_not_an_additional_slice(self):
        chart = overview.dispatch_progress([row()])["tons"]
        self.assertEqual(chart["total"], 10)
        self.assertEqual([p["pct"] for p in chart["series"]], [80, 20])
        self.assertEqual([p["value"] for p in chart["series"]], [8, 2])

    def test_unknown_billed_or_dispatched_weight_excludes_whole_invoice(self):
        rows = [row(), row(2, invoiced_weight_missing_rows=1), row(3, dispatched_weight_missing_rows=1)]
        chart = overview.dispatch_progress(rows)["tons"]
        self.assertEqual(chart["measured_invoices"], 1)
        self.assertEqual(chart["excluded_invoices"], 2)
        self.assertTrue(chart["partial"])
        self.assertEqual(chart["total"], 10)

    def test_mixed_valid_and_unknown_pending_details_are_not_treated_as_complete_weight(self):
        lines = [{"invoice_id": [1, "FA1"], "pending_qty": 1, "pending_weight": 2000},
                 {"invoice_id": [1, "FA1"], "pending_qty": 1, "pending_weight": 0}]
        chart = overview.dispatch_progress([row()], lines)["tons"]
        self.assertFalse(chart["available"])
        self.assertEqual(chart["excluded_invoices"], 1)

    def test_returns_quality_flags_and_non_reconciling_weights_are_excluded(self):
        rows = [row(has_adjustment=True), row(2, quality_issue=True), row(3, invoiced_weight=5000)]
        chart = overview.dispatch_progress(rows)["tons"]
        self.assertFalse(chart["available"])
        self.assertEqual(chart["excluded_invoices"], 3)
        self.assertEqual(overview.dispatch_progress(rows)["invoices"]["total"], 3)

    def test_zero_unknown_or_negative_weights_do_not_form_misleading_slices(self):
        for change in ({"pending_weight": 0}, {"pending_weight": -1}, {"invoiced_weight": 0}, {"dispatched_weight": float("nan")}):
            self.assertFalse(overview.dispatch_progress([row(**change)])["tons"]["available"])

    def test_empty_chart_has_no_percentage_and_complete_dispatch_has_zero_pending(self):
        self.assertIsNone(overview.dispatch_progress([])["invoices"]["series"][1]["pct"])
        chart = overview.dispatch_progress([row(pending=False, dispatched_weight=10000)])["tons"]
        self.assertEqual([p["pct"] for p in chart["series"]], [100, 0])

    def test_agreement_totals_reconcile_tons_and_pallets_with_all_pending_rows(self):
        rows = [row(pending_pallets=2.5, pending_lines=1), row(2, sla_days=9, pending_pallets=3, pending_lines=1),
                row(3, sla_configured=False, eligible=False, pending_pallets=1.25, pending_lines=1)]
        result = overview.pending_by_agreement(rows)
        self.assertTrue(result["reconciled"])
        self.assertEqual(result["totals"]["pending"], 3)
        self.assertEqual(result["totals"]["pending_tons"], 6)
        self.assertEqual(result["totals"]["pending_pallets"], 6.75)

    def test_real_source_rounding_difference_is_explicit_without_changing_weights(self):
        result = overview.pending_by_agreement([row(pending_weight=141146.05), row(2, sla_days=9, pending_weight=889465.71)])
        self.assertAlmostEqual(result["totals"]["pending_tons"], 1030.61176)
        self.assertAlmostEqual(result["groups"][0]["pending_tons"], 141.14605)
        self.assertEqual(result["rounding"]["tons"], -.01)
        self.assertTrue(result["reconciled"])

    def test_positive_rounding_difference_and_fractional_pallets(self):
        result = overview.pending_by_agreement([row(pending_weight=14, pending_pallets=1.005),
            row(2, sla_days=9, pending_weight=14, pending_pallets=1.005)])
        self.assertEqual(result["rounding"], {"tons": .01, "pallets": -.01})
        self.assertEqual(result["totals"]["pending_pallets"], 2.01)

    def test_partial_pallet_availability_survives_grouping(self):
        result = overview.pending_by_agreement([row(pending_pallets=2.5, pending_lines=1),
            row(2, pending_pallets=0, pending_pallets_missing_rows=1, pending_lines=1)])
        self.assertEqual(result["totals"]["pending_pallets"], 2.5)
        self.assertEqual(result["totals"]["pending_pallets_missing_rows"], 1)
        self.assertEqual(result["totals"]["pending_lines"], 2)

    def test_plan_scope_difference_is_explained_as_other_modalities(self):
        rows = [row(), row(2, delivery="Cliente Retira", pending_weight=3000)]
        result = overview.pending_plan_reconciliation(rows, {"scope": "transcash", "pending_tons": 2})
        self.assertEqual((result["total_tons"], result["planned_tons"], result["outside_plan_tons"]), (5, 2, 3))
        self.assertEqual(result["outside_plan_invoices"], 1)
        self.assertFalse(result["same_scope"])
        self.assertTrue(result["detail_matches"])

    def test_all_filtered_plan_and_invoice_total_agree(self):
        rows = [row(), row(2, delivery="Cliente Retira", pending_weight=3000)]
        result = overview.pending_plan_reconciliation(rows, {"scope": "filtered", "pending_tons": 5})
        self.assertTrue(result["same_scope"])
        self.assertTrue(result["detail_matches"])
        self.assertEqual(result["total_tons"], result["planned_tons"])

    def test_missing_plan_detail_is_not_mislabeled_as_excluded_delivery(self):
        result = overview.pending_plan_reconciliation([row()], {"scope": "transcash", "pending_tons": 0})
        self.assertFalse(result["detail_matches"])
        self.assertEqual(result["unallocated_tons"], 2)
        self.assertEqual(result["outside_plan_tons"], 0)

    def test_agreement_mismatch_is_detected_instead_of_silently_claiming_balance(self):
        stats = overview.summarize([row()])
        stats["pending_tons"] = 99
        self.assertFalse(overview.pending_by_agreement([row()], stats=stats)["reconciled"])


class OverviewDashboardTests(unittest.TestCase):
    setUp = dashboard_tests.DashboardTests.setUp

    def test_agreements_and_pie_share_the_applied_invoice_date_filter(self):
        result = self.service.get_data({"date_from": "2026-02-02", "date_to": "2026-02-02"})
        self.assertEqual(result["agreements"]["pending"], 1)
        self.assertEqual(result["agreements"]["groups"][0]["pending_tons"], 18)
        self.assertEqual(result["dispatch_progress"]["invoices"]["total"], 1)

    def test_agreement_drilldown_uses_exact_current_filtered_ids_and_views(self):
        filters = {"date_from": "2026-02-02", "date_to": "2026-02-02"}
        action = self.service.get_detail_action(filters, "agreement", "calendar:3")
        self.assertIn(("id", "in", [3]), action["domain"])
        self.assertIn(("is_current", "=", True), action["domain"])
        self.assertEqual(action["views"][0], (False, "list"))
        with self.assertRaises(dashboard_tests.module.ValidationError):
            self.service.get_detail_action(filters, "agreement", "calendar:999")


if __name__ == "__main__":
    unittest.main()
