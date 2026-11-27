"""Run without Odoo: python3 -m unittest discover -s .../tests -p '*standalone.py'."""
from pathlib import Path
from datetime import date
from importlib.util import spec_from_file_location, module_from_spec
import unittest

ROOT = Path(__file__).resolve().parents[1]


def load(name):
    spec = spec_from_file_location(name, ROOT / "services" / (name + ".py"))
    result = module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


e = load("engine")
x = load("xlsx_reader")


def line(**kwargs):
    result = {"TipoFactura": "FA", "NumeroFactura": "100", "Factura": "001-1", "Establecimiento": "Matriz", "FechaFactura": "2026-10-01",
        "CodCliente": "C1", "Cliente": "Cliente", "Ciudad": "Guayaquil", "CodProducto": "P1", "CodBodega": "B1", "Bodega": "Matriz",
        "Cond_Entrega": "Entrega Transcash", "Facturado": 10, "DespachoFisico": 0, "AjusteDevolucion": 0, "Pendiente": 10,
        "UltimoDespacho": None, "PesoPendiente": 20}
    result.update(kwargs)
    return result


def inv(rows=None, cutoff="2026-10-10"):
    rows = rows or [line()]
    return e.aggregate_invoice(e.invoice_key(rows[0]), rows, cutoff)


def pack(days=2, day_type="calendar"):
    return {"rules": [{"id": 1, "city_key": "GUAYAQUIL", "delivery_key": "", "max_days": days, "day_type": day_type}], "holidays": []}


class EngineTests(unittest.TestCase):
    def test_distinct_invoice_not_product_rows(self):
        rows = [line(), line(CodProducto="P2"), line(NumeroFactura="101")]
        groups = list(e.iter_invoice_groups(iter(rows)))
        self.assertEqual(len(groups), 2)
        self.assertEqual(sorted(len(r) for _, r in groups), [1, 2])

    def test_warehouse_summary_without_sku_is_supported(self):
        first, second = line(), line(CodBodega="B2", Bodega="Otra bodega")
        for row in (first, second):
            row.pop("CodProducto")
        result = inv([first, second])
        self.assertEqual(result["source_grain"], "warehouse")
        self.assertNotIn("lineas_duplicadas", result["quality_flags"])
        self.assertEqual(result["warehouse"], "VARIAS BODEGAS")

    def test_mixed_summary_and_product_rows_are_invalid(self):
        second = line(CodBodega="B2")
        second.pop("CodProducto")
        self.assertIn("granularidad_mixta", inv([line(), second])["quality_flags"])

    def test_positive_pending_not_netted(self):
        result = inv([line(), line(CodProducto="P2", Pendiente=-10, DespachoFisico=20)])
        self.assertTrue(result["pending"])
        self.assertEqual(result["pending_lines"], 1)
        self.assertIn("saldo_negativo", result["quality_flags"])

    def test_partial_invoice(self):
        result = inv([line(DespachoFisico=5, Pendiente=5, UltimoDespacho="2026-10-02")])
        self.assertEqual(result["state"], "partial")
        self.assertFalse(result["completion_date"])

    def test_completion_requires_all_lines(self):
        result = inv([line(DespachoFisico=10, Pendiente=0, UltimoDespacho="2026-10-02"), line(CodProducto="P2")])
        self.assertTrue(result["pending"])
        self.assertFalse(result["physically_completed"])

    def test_completion_latest_product_dispatch(self):
        result = inv([line(DespachoFisico=10, Pendiente=0, UltimoDespacho="2026-10-02"), line(CodProducto="P2", DespachoFisico=10, Pendiente=0, UltimoDespacho="2026-10-04")])
        self.assertEqual(result["completion_date"], "2026-10-04")
        self.assertEqual(e.evaluate(result, pack())["lead_days"], 3)

    def test_return_does_not_prove_dispatch(self):
        result = inv([line(Pendiente=0, AjusteDevolucion=10)])
        self.assertEqual(result["state"], "adjusted")
        self.assertFalse(result["physically_completed"])
        self.assertEqual(e.evaluate(result, pack())["sla_status"], "adjusted")

    def test_missing_completion_date(self):
        result = inv([line(Pendiente=0, DespachoFisico=10)])
        self.assertIn("sin_fecha_despacho", result["quality_flags"])
        self.assertFalse(result["completion_date"])

    def test_missing_city_visible(self):
        self.assertIn("sin_ciudad", inv([line(Ciudad="")])["quality_flags"])

    def test_duplicate_rows_are_flagged(self):
        self.assertIn("lineas_duplicadas", inv([line(), line()])["quality_flags"])

    def test_future_dispatch_is_invalid(self):
        result = inv([line(DespachoFisico=10, Pendiente=0, UltimoDespacho="2026-10-11")])
        self.assertEqual(e.evaluate(result, pack())["sla_status"], "invalid")

    def test_chronology_negative_never_zero_lead(self):
        result = inv([line(DespachoFisico=10, Pendiente=0, UltimoDespacho="2026-09-30")])
        self.assertIsNone(e.evaluate(result, pack())["lead_days"])

    def test_calendar_deadline(self):
        self.assertEqual(e.due_date("2026-10-02", 2), date(2026, 10, 4))

    def test_business_deadline_skips_weekend(self):
        self.assertEqual(e.due_date("2026-10-02", 2, "business"), date(2026, 10, 6))

    def test_business_deadline_skips_configured_holiday(self):
        self.assertEqual(e.due_date("2026-10-02", 2, "business", ["2026-10-05"]), date(2026, 10, 7))

    def test_day_zero(self):
        self.assertEqual(e.due_date("2026-10-03", 0, "business"), date(2026, 10, 3))

    def test_end_of_deadline_day_is_still_in_time(self):
        result = e.evaluate(inv(cutoff="2026-10-03"), pack())
        self.assertEqual(result["sla_status"], "due_today")
        self.assertFalse(result["mature"])

    def test_completed_on_deadline_is_on_time(self):
        result = e.evaluate(inv([line(DespachoFisico=10, Pendiente=0, UltimoDespacho="2026-10-03")]), pack())
        self.assertTrue(result["on_time"])

    def test_open_overdue_is_mature(self):
        result = e.evaluate(inv(), pack())
        self.assertEqual(result["sla_status"], "overdue")
        self.assertTrue(result["mature"])

    def test_missing_sla_is_not_zero_percent(self):
        result = e.summarize([e.evaluate(inv(), {"rules": []})])
        self.assertIsNone(result["mature_compliance"])
        self.assertEqual(result["no_rule"], 1)
        self.assertFalse(result["overdue_available"])
        self.assertEqual(result["pending_unassessed"], 1)

    def test_mature_denominator_includes_overdue_open(self):
        timely = e.evaluate(inv([line(DespachoFisico=10, Pendiente=0, UltimoDespacho="2026-10-02")]), pack())
        late = e.evaluate(inv([line(DespachoFisico=10, Pendiente=0, UltimoDespacho="2026-10-05")]), pack())
        overdue = e.evaluate(inv(), pack())
        open_in_time = e.evaluate(inv(cutoff="2026-10-02"), pack())
        result = e.summarize([timely, late, overdue, open_in_time])
        self.assertEqual(result["mature_count"], 3)
        self.assertAlmostEqual(result["mature_compliance"], 100 / 3)
        self.assertEqual(result["completed_compliance"], 50)

    def test_percentages_are_not_averaged_across_cities(self):
        timely = e.evaluate(inv([line(DespachoFisico=10, Pendiente=0, UltimoDespacho="2026-10-02")]), pack())
        overdue = e.evaluate(inv(), pack())
        self.assertAlmostEqual(e.summarize([timely] + [overdue] * 9)["mature_compliance"], 10)

    def test_specific_rule_wins(self):
        policies = pack()
        policies["rules"].append({"id": 2, "city_key": "", "delivery_key": "", "max_days": 10, "day_type": "calendar"})
        self.assertEqual(e.pick_policy(inv(), policies)["id"], 1)

    def test_city_and_delivery_is_most_specific(self):
        policies = pack()
        policies["rules"].append({"id": 2, "city_key": "GUAYAQUIL", "delivery_key": "ENTREGA TRANSCASH", "max_days": 4, "day_type": "calendar"})
        self.assertEqual(e.pick_policy(inv(), policies)["id"], 2)

    def test_historical_validity(self):
        policies = pack()
        policies["rules"][0]["valid_from"] = "2026-10-02"
        self.assertIsNone(e.pick_policy(inv(), policies))

    def test_ambiguous_policy_rejected(self):
        policies = pack()
        policies["rules"].append(dict(policies["rules"][0]))
        with self.assertRaises(ValueError): e.pick_policy(inv(), policies)

    def test_normalize_city(self):
        self.assertEqual(e.normalize("  Santo   Domíngo "), "SANTO DOMINGO")

    def test_nan_rejected(self):
        with self.assertRaises(ValueError): e.number(float("nan"))

    def test_missing_quantity_blocks_snapshot(self):
        with self.assertRaises(ValueError): inv([line(Pendiente=None)])

    def test_quantities_must_reconcile(self):
        self.assertIn("cantidades_no_concilian", inv([line(Pendiente=9)])["quality_flags"])

    def test_reported_dispatch_includes_adjustments(self):
        self.assertNotIn("despachado_no_concilia", inv([line(DespachoFisico=8, AjusteDevolucion=2, Despachado=10, Pendiente=0, UltimoDespacho="2026-10-02")])["quality_flags"])

    def test_uniform_same_day_dates_raise_signal(self):
        results = [e.evaluate(inv([line(FechaFactura="2026-10-%02d" % (i % 9 + 1), DespachoFisico=10, Pendiente=0, UltimoDespacho="2026-10-%02d" % (i % 9 + 1))]), pack()) for i in range(30)]
        self.assertTrue(e.summarize(results)["same_day_warning"])

    def test_single_day_cohort_does_not_raise_uniform_date_signal(self):
        result = e.evaluate(inv([line(DespachoFisico=10, Pendiente=0, UltimoDespacho="2026-10-01")]), pack())
        self.assertFalse(e.summarize([result] * 30)["same_day_warning"])

    def test_percentile_interpolated(self):
        self.assertAlmostEqual(e.percentile([0, 1, 2, 10], .9), 7.6)

    def test_grouping_unknown_dimension_rejected(self):
        with self.assertRaises(ValueError): e.grouped([], "__class__")

    def test_excel_serial_date(self):
        self.assertEqual(x.excel_date(46323), "2026-10-28")

    def test_excel_1904_date(self):
        self.assertEqual(x.excel_date(0, True), "1904-01-01")

    def test_unknown_workbook_rejected(self):
        with self.assertRaises(ValueError): list(x.iter_xlsx_rows(b"not an excel"))


if __name__ == "__main__":
    unittest.main()
