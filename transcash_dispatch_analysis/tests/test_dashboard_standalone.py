"""Real dashboard service against a bounded in-memory read ORM, not PostgreSQL."""
from datetime import date
from types import SimpleNamespace
import unittest

from test_import_queue_standalone import load_model

module = load_model("dashboard")
from dispatch_queue_test.services.engine import evaluate


class Records(list):
    def mapped(self, field): return Records()


class EmptyModel:
    def search(self, *args, **kwargs): return Records()


class InvoiceModel:
    def __init__(self, rows): self.rows = rows
    def matching(self, domain):
        def matches(row, term):
            key, op, value = term
            actual = row.get(key)
            if isinstance(actual, list): actual = actual[0]
            return {"=":lambda:actual == value,"in":lambda:actual in value,
                    ">=":lambda:actual >= value,"<=":lambda:actual <= value,
                    ">":lambda:actual > value}[op]()
        return [row for row in self.rows if all(matches(row,term) for term in domain)]
    def search_count(self, domain): return len(self.matching(domain))
    def search_read(self, domain, fields):
        return [{"id":r["id"], **{key:r.get(key) for key in fields}} for r in self.matching(domain)]
    def read_group(self, domain, fields, groups, **kwargs):
        return [{groups[0]:r[groups[0]]} for r in self.matching(domain)]


class Environment:
    su = True
    companies = SimpleNamespace(ids=[1])
    user = SimpleNamespace(has_group=lambda name:True)
    def __init__(self, rows, lines):
        company = SimpleNamespace(id=1,name="Main")
        self.models = {"dispatch.invoice":InvoiceModel(rows), "dispatch.invoice.line":InvoiceModel(lines),
            "res.company":SimpleNamespace(browse=lambda ids:[company] if 1 in ids else []),
            "dispatch.transport.settings":SimpleNamespace(_planning_packs=lambda companies:{1:{"company_name":"Main",
                "vehicles":[{"id":1,"name":"10 t","capacity_tons":10,"utilization_pct":90}]}}),
            **{name:EmptyModel() for name in ("dispatch.board","dispatch.source","dispatch.snapshot")}}
    def __getitem__(self, name): return self.models[name]


def data():
    base = {"source_id":[1,"ERP"],"company_id":[1,"Main"],"snapshot_state":"ready", "quality_issue":False,
        "quality_flags":[],"city":"GUAYAQUIL","delivery":"Entrega Transcash","warehouse":"A",
        "cutoff_date":"2026-02-05","pending_lines":1,"pending_boxes":0,"pending_pallets":0,
        "physically_completed":False,"has_adjustment":False,"source_warnings":[],"pending":True}
    rows = [{**base,"id":1,"name":"A","invoice_date":"2026-01-01","pending":False,"physically_completed":True,
                "completion_date":"2026-01-02","pending_weight":0},
            {**base,"id":2,"name":"B","invoice_date":"2026-02-01","pending_weight":9000},
            {**base,"id":3,"name":"C","invoice_date":"2026-02-02","pending_weight":18000}]
    pack={"rules":[{"id":1,"city_key":"GUAYAQUIL","delivery_key":"","max_days":3,"day_type":"calendar"}]}
    rows = [evaluate(r,pack) for r in rows]
    for row in rows: row["lead_available"] = row["lead_days"] is not None
    lines=[{"id":i,"invoice_id":[i,"FA"],"warehouse_code":"A","warehouse":"Origin A",
        "pending_qty":1,"pending_weight":weight,"pending_pallets":0} for i,weight in ((2,9000),(3,18000))]
    return rows, lines


class DashboardTests(unittest.TestCase):
    def setUp(self):
        self.rows,self.lines = data()
        self.service = module.DispatchDashboard()
        self.service.env = Environment(self.rows,self.lines)

    def test_date_filter_reaches_kpis_and_transport_plan(self):
        result = self.service.get_data({"date_from":"2026-02-01","date_to":"2026-02-28"})
        self.assertEqual(result["stats"]["total"],2)
        self.assertEqual(result["stats"]["mature_compliance"],0)
        self.assertEqual(result["stats"]["mature_count"],1)
        self.assertEqual(result["stats"]["pending_tons"],27)
        self.assertEqual(result["transport"]["pending_tons"],27)
        self.assertEqual(result["transport"]["pending_invoices"],2)
        self.assertEqual(result["period"]["date_from"],"2026-02-01")

    def test_full_period_uses_counts_instead_of_mean_percentages(self):
        result = self.service.get_data()
        self.assertEqual(result["stats"]["mature_compliance"],50)
        self.assertEqual(result["period"]["date_from"],"2026-01-01")

    def test_empty_range_has_no_percentage_or_fleet_demand(self):
        result = self.service.get_data({"date_from":"2026-03-01"})
        self.assertIsNone(result["stats"]["mature_compliance"])
        self.assertEqual(result["transport"]["required_vehicles"],0)

    def test_reversed_dates_and_unknown_plan_scope_are_rejected(self):
        with self.assertRaises(module.ValidationError):
            self.service.get_data({"date_from":"2026-02-05","date_to":"2026-01-01"})
        with self.assertRaises(module.ValidationError):
            self.service.get_data({"planning_scope":"arbitrary"})

    def test_company_filter_and_invoice_date_basis_are_retained(self):
        domain = self.service._domain({"date_from":"2026-02-01","date_to":"2026-02-02"})
        self.assertIn(("company_id","in",[1]), domain)
        self.assertIn(("invoice_date",">=","2026-02-01"), domain)
        self.assertIn(("snapshot_state","=","ready"), domain)


if __name__ == "__main__":
    unittest.main()
