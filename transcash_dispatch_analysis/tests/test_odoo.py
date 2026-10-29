from odoo.tests import TransactionCase, tagged
from odoo.exceptions import ValidationError, AccessError
from unittest.mock import patch
import base64
from ..models import snapshot as snapshot_module


@tagged("post_install", "-at_install")
class TestDispatchIntegration(TransactionCase):
    def setUp(self):
        super().setUp()
        self.source = self.env["dispatch.source"].create({"name": "Test", "code": "TEST-DISPATCH", "company_id": self.env.company.id})
        self.rule = self.env["dispatch.sla"].search([("company_id", "=", self.env.company.id), ("city_key", "=", "GUAYAQUIL")], limit=1)
        self.rule.max_days = 2
        self.row = {"TipoFactura": "FA", "NumeroFactura": "1", "Factura": "001", "FechaFactura": "2026-01-01", "Ciudad": "Guayaquil", "CodProducto": "A", "CodBodega": "X", "Facturado": 1, "DespachoFisico": 0, "Pendiente": 1}

    def _snapshot(self, key):
        value = self.source.api_start_batch(key, "2026-01-10")
        result = self.env["dispatch.snapshot"].browse(value["id"])
        result.api_append_chunk(0, [self.row])
        result.api_finalize(1, 1)
        return result

    def test_api_retry_is_idempotent(self):
        snapshot = self._snapshot("idempotent")
        self.assertTrue(snapshot.api_append_chunk(0, [self.row])["duplicate"])
        self.assertEqual(self.source.api_start_batch("idempotent", "2026-01-10")["id"], snapshot.id)
        with self.assertRaises(ValidationError): snapshot.api_append_chunk(0, [{**self.row, "Pendiente": 0}])

    def test_atomic_snapshot_activation(self):
        first = self._snapshot("first")
        first._prepare()
        self.assertFalse(self.source.active_snapshot_id)
        first._load_next()
        self.assertEqual(self.source.active_snapshot_id, first)
        second = self._snapshot("second")
        second._prepare()
        self.assertEqual(self.source.active_snapshot_id, first)
        second._load_next()
        self.assertEqual(self.source.active_snapshot_id, second)
        self.assertEqual(first.state, "archived")
        self.assertEqual(self.env["dispatch.dashboard"].get_data({"source_id": self.source.id})["stats"]["pending"], 1)

    def test_older_cutoff_never_overwrites_newer(self):
        latest = self._snapshot("latest")
        latest._prepare(); latest._load_next()
        old_id = self.source.api_start_batch("old", "2026-01-05")["id"]
        old = self.env["dispatch.snapshot"].browse(old_id)
        old.api_finalize(0, 0)
        old._prepare()
        self.assertEqual(self.source.active_snapshot_id, latest)
        self.assertEqual(old.state, "archived")

    def test_reader_cannot_ingest(self):
        user = self.env["res.users"].create({"name": "Reader", "login": "dispatch_reader_test", "company_id": self.env.company.id,
            "company_ids": [(6, 0, [self.env.company.id])], "groups_id": [(6, 0, [self.env.ref("transcash_dispatch_analysis.group_dispatch_user").id])]})
        with self.assertRaises(AccessError): self.source.with_user(user).api_start_batch("forbidden", "2026-01-10")

    def test_other_company_not_visible(self):
        company = self.env["res.company"].create({"name": "Another dispatch company"})
        foreign = self.env["dispatch.source"].create({"name": "Foreign", "code": "FOREIGN", "company_id": company.id})
        user = self.env["res.users"].create({"name": "Operator", "login": "dispatch_operator_test", "company_id": self.env.company.id,
            "company_ids": [(6, 0, [self.env.company.id])], "groups_id": [(6, 0, [self.env.ref("transcash_dispatch_analysis.group_dispatch_operator").id])]})
        with self.assertRaises(AccessError): foreign.with_user(user).api_start_batch("cross-company", "2026-01-10")

    def test_policy_reapply_preserves_history(self):
        first = self._snapshot("policy-first")
        first._prepare(); first._load_next()
        rule = self.env["dispatch.sla"].search([("company_id", "=", self.env.company.id), ("city_key", "=", "GUAYAQUIL")], limit=1)
        rule.max_days = 20
        self.assertEqual(first.invoice_ids.sla_days, 2)
        action = first.action_recalculate()
        second = self.env["dispatch.snapshot"].browse(action["params"]["snapshot_id"])
        second._prepare(); second._load_next()
        self.assertEqual(second.invoice_ids.sla_days, 20)
        self.assertEqual(first.invoice_ids.sla_days, 2)

    def test_interactive_import_with_cron_disabled(self):
        self.env.ref("transcash_dispatch_analysis.cron_dispatch_import").active = False
        snapshot = self._snapshot("interactive-no-cron")
        self.assertEqual(snapshot.process_import_step()["state"], "loading")
        result = snapshot.process_import_step()
        self.assertTrue(result["done"])
        self.assertEqual(result["loaded_invoices"], 1)

    def test_interactive_resume_preserves_completed_blocks(self):
        self.env.ref("transcash_dispatch_analysis.cron_dispatch_import").active = False
        ident = self.source.api_start_batch("interactive-resume", "2026-01-10")["id"]
        snapshot = self.env["dispatch.snapshot"].browse(ident)
        snapshot.api_append_chunk(0, [self.row, {**self.row, "NumeroFactura": "2"}])
        snapshot.api_finalize(1, 2)
        with patch.object(snapshot_module, "BATCH_SIZE", 1):
            snapshot.process_import_step()
        self.assertEqual(snapshot.process_import_step()["loaded_invoices"], 1)
        self.assertEqual(snapshot.get_import_progress()["loaded_invoices"], 1)
        self.assertTrue(snapshot.process_import_step()["done"])
        self.assertTrue(snapshot.process_import_step()["done"])
        self.assertEqual(len(snapshot.invoice_ids), 2)

    def test_interactive_bad_excel_returns_error(self):
        snapshot = self.env["dispatch.snapshot"].create({"name": "Invalid Excel", "source_id": self.source.id,
            "company_id": self.env.company.id, "cutoff_date": "2026-01-10", "input_type": "xlsx",
            "file_name": "invalid.xlsx", "raw_file": base64.b64encode(b"not a workbook")})
        result = snapshot.process_import_step()
        self.assertTrue(result["failed"])
        self.assertIn("XLSX", result["error_message"])

    def test_new_cities_get_defaults_before_policy_capture(self):
        self.rule.max_days = 3
        self.row["Ciudad"] = "Cuenca"
        snapshot = self._snapshot("new-city-default")
        snapshot._prepare(); snapshot._load_next()
        self.assertEqual(snapshot.invoice_ids.sla_days, 9)
        self.assertEqual(str(snapshot.invoice_ids.deadline), "2026-01-10")
        rule = self.env["dispatch.sla"].search([("company_id", "=", self.env.company.id), ("city_key", "=", "CUENCA")])
        self.assertEqual(len(rule), 1)
        rule.max_days = 15
        second = self._snapshot("new-city-keeps-edit")
        second._prepare(); second._load_next()
        self.assertEqual(second.invoice_ids.sla_days, 15)
        self.assertEqual(snapshot.invoice_ids.sla_days, 9)

    def test_defaults_and_update_backfill_are_idempotent(self):
        company = self.env["res.company"].create({"name": "Default city company"})
        self.env["dispatch.source"].create({"name": "Defaults", "code": "DEFAULTS", "company_id": company.id})
        rules = self.env["dispatch.sla"].sudo()
        rule = rules.search([("company_id", "=", company.id), ("city_key", "=", "GUAYAQUIL")])
        self.assertEqual(rule.max_days, 3)
        rule.max_days = 7
        rules._ensure_city_defaults(company, [" guayaquil ", "GUAYAQUIL", "Quito", "", "SIN CIUDAD"])
        rules._initialize_city_defaults()
        self.assertEqual(rule.max_days, 7)
        self.assertEqual(len(rules.search([("company_id", "=", company.id)])), 2)

    def test_new_rule_defaults_and_explicit_override(self):
        rules = self.env["dispatch.sla"]
        guayaquil = rules.create({"city": "Guayaquil", "delivery": "Test automatic default"})
        other = rules.create({"city": "Ciudad de prueba nueva"})
        explicit = rules.create({"city": "Guayaquil", "delivery": "Test explicit zero", "max_days": 0})
        self.assertEqual(guayaquil.max_days, 3)
        self.assertEqual(other.max_days, 9)
        self.assertEqual(explicit.max_days, 0)

    def test_update_detects_city_from_already_imported_invoices(self):
        snapshot = self._snapshot("legacy-city")
        snapshot._prepare(); snapshot._load_next()
        snapshot.invoice_ids.city = "CIUDAD LEGADA"
        self.env["dispatch.sla"]._initialize_city_defaults()
        rule = self.env["dispatch.sla"].search([("company_id", "=", self.env.company.id), ("city_key", "=", "CIUDAD LEGADA")])
        self.assertEqual(rule.max_days, 9)
        self.assertEqual(snapshot.invoice_ids.sla_days, 2)

    def test_dashboard_recalculation_opens_interactive_progress(self):
        snapshot = self._snapshot("open-recalculation")
        snapshot._prepare(); snapshot._load_next()
        result = self.env["dispatch.dashboard"].request_recalculation({"source_id":self.source.id})
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["action"]["tag"], "transcash_dispatch_import_progress")
        self.assertNotEqual(result["action"]["params"]["snapshot_id"], snapshot.id)
