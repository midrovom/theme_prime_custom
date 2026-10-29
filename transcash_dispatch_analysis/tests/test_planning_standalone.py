"""Capacity and reporting regression tests; runnable without Odoo."""
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import ModuleType
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
pkg = ModuleType("dispatch_planning_tests")
pkg.__path__ = [str(ROOT / "services")]
sys.modules[pkg.__name__] = pkg


def load(name):
    spec = spec_from_file_location("dispatch_planning_tests." + name, ROOT / "services" / (name + ".py"))
    module = module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


engine = load("engine")
planning = load("planning")


def invoice(ident=1, **values):
    return {"id": ident, "pending": True, "city": "Guayaquil", "company_id": [1, "Main"],
            "source_id": [1, "ERP"], "delivery": "Entrega Transcash", **values}


def line(ident=1, **values):
    return {"invoice_id": [ident, "FA"], "warehouse_code": "A", "warehouse": "Warehouse A",
            "pending_qty": 1, "pending_weight": 54000, **values}


def pack(**values):
    return {1: {"company_name": "Main", "vehicles": [{"id": 1, "name": "10t", "capacity_tons": 10,
        "utilization_pct": 90}], "settings": {"target_days": 3, "available_vehicles": 1, "trips_per_day": 1}, **values}}


class PlanningTests(unittest.TestCase):
    def test_tonnes_are_metric_tonnes_only_for_pending(self):
        rows = [invoice(pending_weight=1234.5), invoice(2, pending_weight=5432.1),
                invoice(3, pending=False, pending_weight=9000)]
        stats = engine.summarize(rows)
        self.assertAlmostEqual(stats["pending_tons"], 6.6666)
        self.assertAlmostEqual(engine.metric_value(rows, "pending_tons"), 6.6666)

    def test_full_trips_and_required_fleet_for_target(self):
        plan = planning.build_transport_plan([invoice()], [line()], pack())
        estimate = plan["lanes"][0]["estimate"]
        self.assertEqual(estimate["useful_tons"], 9)
        self.assertEqual(estimate["trips"], 6)
        self.assertEqual(estimate["required_vehicles"], 2)
        self.assertEqual(estimate["additional_vehicles"], 1)
        self.assertEqual(estimate["days_current_fleet"], 6)

    def test_fractional_daily_cycles_do_not_overstate_capacity(self):
        plan = planning.build_transport_plan([invoice()], [line(pending_weight=27000)],
            pack(settings={"target_days": 3, "available_vehicles": 1, "trips_per_day": .5}))
        estimate = plan["lanes"][0]["estimate"]
        self.assertEqual(estimate["trips_per_vehicle_in_target"], 1)
        self.assertEqual(estimate["required_vehicles"], 3)
        self.assertEqual(estimate["days_current_fleet"], 6)

    def test_discrete_waves_are_required_for_current_fleet(self):
        estimate = planning.vehicle_estimate(27000, pack()[1]["vehicles"][0],
            {"target_days": 10, "available_vehicles": 2, "trips_per_day": .4})
        self.assertEqual(estimate["days_current_fleet"], 5)

    def test_target_shorter_than_a_cycle_is_infeasible(self):
        plan = planning.build_transport_plan([invoice()], [line()],
            pack(settings={"target_days": 1, "available_vehicles": 1, "trips_per_day": .5}))
        self.assertIsNone(plan["required_vehicles"])
        self.assertIsNone(plan["additional_vehicles"])
        self.assertIn("ciclo", " ".join(plan["lanes"][0]["issues"]))

    def test_zero_fleet_has_no_clearance_day_estimate(self):
        plan = planning.build_transport_plan([invoice()], [line()],
            pack(settings={"target_days": 3, "available_vehicles": 0, "trips_per_day": 1}))
        self.assertIsNone(plan["days_current_fleet"])
        self.assertEqual(plan["required_vehicles"], 2)
        self.assertEqual(plan["additional_vehicles"], 2)

    def test_city_override_and_origin_override_have_priority(self):
        routes = [{"city": "Guayaquil", "target_days": 2, "available_vehicles": 3, "trips_per_day": 1},
                  {"city": "GUAYAQUIL", "warehouse_code": "A", "target_days": 4, "available_vehicles": 2, "trips_per_day": .5}]
        result = planning.build_transport_plan([invoice()], [line()], pack(routes=routes))
        self.assertEqual(result["lanes"][0]["estimate"]["target_days"], 4)
        self.assertEqual(result["lanes"][0]["estimate"]["available_vehicles"], 2)
        other = planning.build_transport_plan([invoice()], [line(warehouse_code="B")], pack(routes=routes))
        self.assertEqual(other["lanes"][0]["estimate"]["target_days"], 2)

    def test_pickups_are_excluded_from_transcash_contracting(self):
        invoices = [invoice(), invoice(2, delivery="Cliente Retira en Almacén")]
        result = planning.build_transport_plan(invoices, [line(), line(2)], pack())
        self.assertEqual(result["pending_invoices"], 1)
        self.assertEqual(result["excluded_invoices"], 1)
        self.assertEqual(result["pending_tons"], 54)
        broader = planning.build_transport_plan(invoices, [line(), line(2)], pack(), "filtered")
        self.assertEqual(broader["pending_invoices"], 2)
        self.assertEqual(broader["pending_tons"], 108)

    def test_distinct_origins_never_share_load_or_vehicles(self):
        result = planning.build_transport_plan([invoice()], [line(pending_weight=1000),
            line(warehouse_code="B", warehouse="Warehouse B", pending_weight=1000)], pack())
        self.assertEqual(len(result["lanes"]), 2)
        self.assertEqual(result["pending_invoices"], 1)
        self.assertEqual(result["trips"], 2)
        self.assertEqual(result["required_vehicles"], 2)

    def test_multiple_products_in_one_lane_count_invoice_once(self):
        result = planning.build_transport_plan([invoice()], [line(pending_weight=1000), line(pending_weight=1000)], pack())
        self.assertEqual(result["lanes"][0]["invoice_count"], 1)
        self.assertEqual(result["trips"], 1)

    def test_sources_and_companies_are_separate(self):
        invoices = [invoice(), invoice(2, source_id=[2, "Second ERP"]), invoice(3, company_id=[2, "Other"])]
        packs = {**pack(), 2:{**pack()[1], "company_name":"Other"}}
        result = planning.build_transport_plan(invoices, [line(), line(2), line(3)], packs)
        self.assertEqual(len(result["lanes"]), 3)
        self.assertEqual(result["required_vehicles"], 6)
        self.assertEqual(result["days_current_fleet"], 6)

    def test_parallel_clearance_uses_maximum_days_not_sum(self):
        result = planning.build_transport_plan([invoice(), invoice(2, city="Quito")],
            [line(pending_weight=9000), line(2, pending_weight=45000)], pack())
        self.assertEqual(result["days_current_fleet"], 5)
        self.assertEqual(result["available_vehicles"], 2)

    def test_unknown_weight_is_visible_and_not_treated_as_zero_work(self):
        result = planning.build_transport_plan([invoice()], [line(pending_weight=0)], pack())
        self.assertFalse(result["complete"])
        self.assertEqual(result["unknown_weight_lines"], 1)
        self.assertIsNone(result["required_vehicles"])

    def test_missing_city_or_origin_blocks_recommendation(self):
        for rows, lines in (([invoice(city="SIN CIUDAD")], [line()]), ([invoice()], [line(warehouse="", warehouse_code="")])):
            result = planning.build_transport_plan(rows, lines, pack())
            self.assertFalse(result["complete"])
            self.assertIsNone(result["lanes"][0]["estimate"])

    def test_missing_detail_never_disappears_from_backlog(self):
        result = planning.build_transport_plan([invoice()], [], pack())
        self.assertEqual(result["pending_invoices"], 1)
        self.assertEqual(len(result["lanes"]), 1)
        self.assertFalse(result["complete"])

    def test_adjustments_and_quality_issues_are_flagged(self):
        result = planning.build_transport_plan([invoice(has_adjustment=True)], [line()], pack())
        self.assertEqual(result["lanes"][0]["review_count"], 1)
        self.assertFalse(result["complete"])
        self.assertEqual(result["pending_tons"], 54)

    def test_smallest_suitable_type_wins_capacity_tie(self):
        vehicles = [{"id":i,"name":str(t),"capacity_tons":t,"utilization_pct":100} for i,t in enumerate((3.5,10,28),1)]
        result = planning.build_transport_plan([invoice()], [line(pending_weight=1000)], pack(vehicles=vehicles))
        self.assertEqual(result["lanes"][0]["estimate"]["capacity_tons"], 3.5)

    def test_fewer_vehicles_is_the_first_recommendation_criterion(self):
        vehicles = [{"id":i,"name":str(t),"capacity_tons":t,"utilization_pct":100} for i,t in enumerate((3.5,10,28),1)]
        result = planning.build_transport_plan([invoice()], [line(pending_weight=50000)], pack(vehicles=vehicles))
        self.assertEqual(result["lanes"][0]["estimate"]["capacity_tons"], 28)
        self.assertEqual(result["lanes"][0]["estimate"]["required_vehicles"], 1)

    def test_preferred_type_overrides_automatic_choice(self):
        vehicles = [{"id":i,"name":str(t),"capacity_tons":t,"utilization_pct":100} for i,t in enumerate((3.5,28),1)]
        result = planning.build_transport_plan([invoice()], [line()],
            pack(vehicles=vehicles, routes=[{"city":"Guayaquil","vehicle_id":1}]))
        self.assertEqual(result["lanes"][0]["estimate"]["capacity_tons"], 3.5)

    def test_no_active_vehicle_returns_missing_configuration(self):
        result = planning.build_transport_plan([invoice()], [line()], pack(vehicles=[]))
        self.assertIsNone(result["required_vehicles"])
        self.assertFalse(result["complete"])

    def test_closed_and_negative_quantity_lines_are_not_planned(self):
        result = planning.build_transport_plan([invoice()], [line(), line(pending_qty=0), line(pending_qty=-3)], pack())
        self.assertEqual(result["pending_tons"], 54)

    def test_empty_backlog_needs_zero_days_and_vehicles(self):
        result = planning.build_transport_plan([], [], pack())
        self.assertEqual(result["required_vehicles"], 0)
        self.assertEqual(result["days_current_fleet"], 0)
        self.assertTrue(result["complete"])

    def test_invalid_scenario_values_rejected(self):
        for key, values in (("target_days", (0, -1, 1.2, float("inf"))),
                            ("available_vehicles", (-1, 1.1)), ("trips_per_day", (0, -1, float("nan")))):
            for value in values:
                with self.assertRaises(ValueError):
                    planning.validate_settings({**planning.DEFAULT_SETTINGS, key:value})

    def test_compliance_is_recomputed_from_period_counts(self):
        rows = [{"invoice_date":"2026-01-01","eligible":True,"physically_completed":True,"mature":True,"on_time":True},
                {"invoice_date":"2026-02-01","eligible":True,"pending":True,"mature":True,"sla_status":"overdue"},
                {"invoice_date":"2026-02-02","eligible":True,"pending":True,"mature":False}]
        february = [r for r in rows if "2026-02-01" <= r["invoice_date"] <= "2026-02-28"]
        self.assertEqual(engine.summarize(rows)["mature_compliance"], 50)
        self.assertEqual(engine.summarize(february)["mature_compliance"], 0)
        self.assertEqual(engine.summarize(february)["mature_count"], 1)


if __name__ == "__main__":
    unittest.main()
