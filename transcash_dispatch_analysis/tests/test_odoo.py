from odoo.tests import TransactionCase, tagged
from odoo.exceptions import ValidationError, AccessError, UserError
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

    def test_transport_defaults_keep_custom_values_on_update(self):
        settings = self.env["dispatch.transport.settings"]
        settings._initialize_transport_defaults()
        record = settings.search([("company_id", "=", self.env.company.id)])
        record.target_days = 7
        vehicle = self.env["dispatch.vehicle.type"].search([("company_id", "=", self.env.company.id), ("code", "=", "REF_5")], limit=1)
        vehicle.write({"capacity_tons": 4.5, "active": False})
        settings._initialize_transport_defaults()
        self.assertEqual(record.target_days, 7)
        self.assertEqual(vehicle.capacity_tons, 4.5)
        self.assertFalse(vehicle.active)
        self.assertEqual(len(self.env["dispatch.vehicle.type"].with_context(active_test=False).search(
            [("company_id", "=", self.env.company.id), ("code", "=", "REF_5")])), 1)

    def test_dashboard_range_tonnes_and_plan_share_same_population(self):
        self.env["dispatch.transport.settings"]._initialize_transport_defaults()
        self.row.update({"Cond_Entrega":"Entrega Transcash", "PesoPendiente":1250, "Bodega":"Bodega X"})
        snapshot = self._snapshot("period-plan")
        snapshot._prepare(); snapshot._load_next()
        service = self.env["dispatch.dashboard"]
        result = service.get_data({"source_id":self.source.id, "date_from":"2026-01-01", "date_to":"2026-01-01"})
        self.assertEqual(result["stats"]["pending_tons"], 1.25)
        self.assertEqual(snapshot.invoice_ids.pending_tons, 1.25)
        self.assertEqual(result["transport"]["pending_tons"], 1.25)
        self.assertEqual(result["period"]["date_from"], "2026-01-01")
        self.assertEqual(result["stats"]["mature_compliance"], 0)
        empty = service.get_data({"source_id":self.source.id, "date_from":"2026-01-02", "date_to":"2026-01-03"})
        self.assertEqual(empty["stats"]["pending_tons"], 0)
        self.assertIsNone(empty["stats"]["mature_compliance"])
        self.assertEqual(empty["transport"]["required_vehicles"], 0)

    def test_transport_scopes_and_multiorigin_are_independent(self):
        self.env["dispatch.transport.settings"]._initialize_transport_defaults()
        self.row.update({"Cond_Entrega":"Cliente Retira en Almacén", "PesoPendiente":9000, "Bodega":"Bodega X"})
        snapshot = self._snapshot("pickup-plan")
        snapshot._prepare(); snapshot._load_next()
        service = self.env["dispatch.dashboard"]
        self.assertEqual(service.get_data({"source_id":self.source.id})["transport"]["pending_invoices"], 0)
        result = service.get_data({"source_id":self.source.id,"planning_scope":"filtered"})
        self.assertEqual(result["transport"]["pending_invoices"], 1)
        self.assertEqual(result["transport"]["pending_tons"], 9)

    def test_transport_settings_validate_and_reader_cannot_change(self):
        self.env["dispatch.transport.settings"]._initialize_transport_defaults()
        record = self.env["dispatch.transport.settings"].search([("company_id", "=", self.env.company.id)])
        with self.assertRaises(ValidationError), self.cr.savepoint():
            record.trips_per_day = 0
        user = self.env["res.users"].create({"name":"Transport reader","login":"dispatch_transport_reader",
            "company_id":self.env.company.id,"company_ids":[(6,0,[self.env.company.id])],
            "groups_id":[(6,0,[self.env.ref("transcash_dispatch_analysis.group_dispatch_user").id])]})
        self.assertTrue(record.with_user(user).read(["target_days"]))
        with self.assertRaises(AccessError):
            record.with_user(user).write({"target_days":12})

    def test_duplicate_route_and_cross_company_vehicle_are_rejected(self):
        route = self.env["dispatch.transport.route"].create({"city":"Guayaquil","warehouse_code":"X"})
        with self.assertRaises(ValidationError), self.cr.savepoint():
            self.env["dispatch.transport.route"].create({"city":" GUAYAQUIL ","warehouse_code":"x"})
        other = self.env["res.company"].create({"name":"Foreign fleet"})
        vehicle = self.env["dispatch.vehicle.type"].create({"name":"Other truck","capacity_tons":10,"company_id":other.id})
        with self.assertRaises(UserError), self.cr.savepoint():
            route.vehicle_id = vehicle
