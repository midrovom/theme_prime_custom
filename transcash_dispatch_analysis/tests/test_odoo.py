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

    def test_prepared_chunk_resumes_from_database_cursor(self):
        ident=self.source.api_start_batch("bounded-cursor","2026-01-10")["id"]
        snapshot=self.env["dispatch.snapshot"].browse(ident)
        rows=[dict(self.row,NumeroFactura="LOAD-%s"%i) for i in range(250)]
        snapshot.api_append_chunk(0,rows);snapshot.api_finalize(1,len(rows));snapshot._prepare()
        chunk=snapshot.chunk_ids.filtered(lambda c:c.phase=="prepared")
        snapshot._load_next();snapshot.invalidate_recordset();chunk.invalidate_recordset()
        self.assertEqual(snapshot.loaded_invoices,100)
        self.assertEqual(chunk.processed_count,100)
        self.assertEqual(len(snapshot.invoice_ids),100)
        try:
            with self.env.cr.savepoint():
                snapshot._load_next()
                raise RuntimeError("Simulated rollback before request commit")
        except RuntimeError:
            pass
        snapshot.invalidate_recordset();chunk.invalidate_recordset()
        self.assertEqual(snapshot.loaded_invoices,100)
        self.assertEqual(chunk.processed_count,100)
        snapshot._load_next();snapshot._load_next()
        self.assertEqual(snapshot.state,"ready")
        self.assertEqual(len(snapshot.invoice_ids),250)

    def test_background_request_does_not_run_heavy_preparation(self):
        snapshot=self._snapshot("background-request")
        self.env.ref("transcash_dispatch_analysis.cron_dispatch_import").active=True
        with patch.object(snapshot_module.DispatchSnapshot,"_prepare",side_effect=AssertionError("HTTP must only schedule")):
            result=snapshot.request_background_processing()
        self.assertTrue(result["background_processing"])
        self.assertEqual(result["state"],"queued")

    def test_background_resumes_old_cursor_and_rolls_back_publication_together(self):
        first = self._snapshot("background-previous")
        first._prepare(); first._load_next()
        ident = self.source.api_start_batch("background-existing-cursor", "2026-01-10")["id"]
        snapshot = self.env["dispatch.snapshot"].browse(ident)
        rows = [dict(self.row, NumeroFactura="BG-%04d" % i) for i in range(600)]
        snapshot.api_append_chunk(0, rows); snapshot.api_finalize(1, len(rows)); snapshot._prepare()
        snapshot._load_next()
        self.assertEqual(snapshot.loaded_invoices, 100)
        background = snapshot.with_context(dispatch_background=True, bin_size=False)
        background._run_import_step()
        snapshot.invalidate_recordset()
        self.assertEqual(snapshot.loaded_invoices, 500)
        self.assertEqual(self.source.active_snapshot_id, first)
        snapshot.background_batch_size = 500
        try:
            with self.env.cr.savepoint():
                background._run_import_step()
                self.assertEqual(snapshot.state, "ready")
                raise RuntimeError("Simulated rollback before cron commit")
        except RuntimeError:
            pass
        snapshot.invalidate_recordset(); self.source.invalidate_recordset()
        self.assertEqual(snapshot.state, "loading")
        self.assertEqual(snapshot.loaded_invoices, 500)
        self.assertEqual(len(snapshot.invoice_ids), 500)
        self.assertEqual(self.source.active_snapshot_id, first)
        background._run_import_step()
        self.assertEqual(snapshot.state, "ready")
        self.assertEqual(len(snapshot.invoice_ids), 600)
        self.assertEqual(len(snapshot.invoice_ids.filtered("is_current")), 600)

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

    def test_double_import_keeps_one_current_business_key(self):
        first=self._snapshot("double-first");first._prepare();first._load_next()
        second=self._snapshot("double-second");second._prepare();second._load_next()
        model=self.env["dispatch.invoice"]
        versions=model.search([("source_id","=",self.source.id)])
        current=versions.filtered("is_current")
        self.assertEqual(len(versions),2)
        self.assertEqual(len(current),1)
        self.assertEqual(current.snapshot_id,second)
        self.assertEqual(current.invoice_key,'["FA","1"]')
        self.assertEqual(first.state,"archived")
        self.assertEqual(self.env["dispatch.dashboard"].get_data({"source_id":self.source.id})["stats"]["pending"],1)

    def test_repeated_detail_updates_instead_of_adding_weight(self):
        ident=self.source.api_start_batch("duplicate-details","2026-01-10")["id"]
        snapshot=self.env["dispatch.snapshot"].browse(ident)
        old={**self.row,"PesoPendiente":9000,"Bodega":"X"}
        newer={**old,"PesoPendiente":4500,"Facturado":1,"DespachoFisico":.5,"Pendiente":.5,"UltimoDespacho":"2026-01-02"}
        snapshot.api_append_chunk(0,[old,newer]);snapshot.api_finalize(1,2)
        snapshot._prepare();snapshot._load_next()
        self.assertEqual(snapshot.total_rows,2)
        self.assertEqual(snapshot.total_invoices,1)
        self.assertEqual(snapshot.duplicate_rows,1)
        self.assertEqual(snapshot.duplicate_updates,1)
        self.assertEqual(len(snapshot.invoice_ids.line_ids),1)
        self.assertEqual(snapshot.invoice_ids.pending_weight,4500)

    def test_warehouse_scope_and_native_favorite(self):
        ident=self.source.api_start_batch("warehouse-scope","2026-01-10")["id"]
        snapshot=self.env["dispatch.snapshot"].browse(ident)
        first={**self.row,"CodBodega":"B1","Bodega":"Warehouse One","PesoPendiente":9000,"PesoDespacho":0,"Cond_Entrega":"Entrega Transcash"}
        second={**first,"CodBodega":"B2","Bodega":"Warehouse Two","PesoPendiente":18000}
        snapshot.api_append_chunk(0,[first,second]);snapshot.api_finalize(1,2)
        snapshot._prepare();snapshot._load_next()
        warehouses=snapshot.invoice_ids.warehouse_ids
        self.assertEqual(len(warehouses),2)
        selected=warehouses.filtered(lambda r:r.code=="B1")
        service=self.env["dispatch.dashboard"]
        filters={"source_id":self.source.id,"warehouse_ids":selected.ids}
        result=service.get_data(filters)
        self.assertEqual(result["stats"]["pending_tons"],9)
        self.assertEqual(result["stats"]["invoiced_tons"],9)
        self.assertEqual(result["transport"]["pending_tons"],9)
        self.assertEqual(result["transport"]["destinations"][0]["invoice_count"],1)
        favorite=service.save_dashboard_filter("Warehouse fixture",filters)
        stored=self.env["ir.filters"].browse(favorite["id"])
        self.assertEqual(stored.user_id,self.env.user)
        self.assertEqual(stored.model_id,"dispatch.invoice.line")
        self.assertIn(favorite["id"],[row["id"] for row in service.get_saved_filters()])

    def test_existing_import_backfill_and_database_audit(self):
        snapshot=self._snapshot("legacy-backfill");snapshot._prepare();snapshot._load_next()
        invoice=snapshot.invoice_ids
        invoice.write({"is_current":False,"invoice_key":'["FA","1","Old establishment"]'})
        self.env["dispatch.invoice"]._initialize_unique_records(self.env.company)
        self.assertTrue(invoice.is_current)
        self.assertEqual(invoice.invoice_key,'["FA","1"]')
        self.assertTrue(invoice.warehouse_ids)
        audit=self.env["dispatch.dashboard"].validate_current_records()
        self.assertEqual(audit["current_duplicate_keys"],0)

    def test_overlapping_sources_publish_only_newest_observation(self):
        first=self._snapshot("overlap-first");first._prepare();first._load_next()
        other=self.env["dispatch.source"].create({"name":"Overlapping fixture","code":"OVERLAP-FIXTURE"})
        ident=other.api_start_batch("overlap-new","2026-01-10")["id"]
        second=self.env["dispatch.snapshot"].browse(ident)
        second.api_append_chunk(0,[{**self.row,"PesoPendiente":8000}]);second.api_finalize(1,1)
        second._prepare();second._load_next()
        versions=first.invoice_ids|second.invoice_ids
        self.assertEqual(len(versions.filtered("is_current")),1)
        self.assertEqual(versions.filtered("is_current").source_id,other)

    def test_pallet_fields_backfill_existing_import_without_reupload(self):
        self.row.update({"PalletsPendientes": 3.5, "PalletsFacturados": 4.25, "PesoPendiente": 9000})
        snapshot = self._snapshot("pallet-backfill")
        snapshot._prepare(); snapshot._load_next()
        invoice = snapshot.invoice_ids
        self.assertEqual(invoice.invoiced_pallets, 4.25)
        self.assertEqual(invoice.pending_pallets, 3.5)
        invoice.line_ids.write({"invoiced_pallets": 0, "invoiced_pallets_available": False, "pending_pallets": 0})
        self.env["dispatch.invoice"]._initialize_unique_records(self.env.company)
        self.assertEqual(invoice.invoiced_pallets, 4.25)
        self.assertEqual(invoice.pending_pallets, 3.5)
        self.assertEqual(invoice.invoiced_pallets_missing_rows, 0)
        self.assertTrue(invoice.line_ids.invoiced_pallets_available)

    def test_kpi_and_warehouse_actions_include_views_and_date_scope(self):
        service = self.env["dispatch.dashboard"]
        filters = {"date_from": "2026-01-01", "date_to": "2026-01-30"}
        action = service.get_detail_action(filters)
        self.assertEqual(action["views"][0], (False, "list"))
        self.assertIn(("invoice_date", ">=", "2026-01-01"), action["domain"])
        warehouse_action = service.get_warehouse_action(filters)
        self.assertTrue(warehouse_action["views"])
        self.assertIn(("invoice_id.invoice_date", ">=", "2026-01-01"), warehouse_action["domain"])

    def test_overview_agreement_and_weight_pie_share_import_and_domain(self):
        self.row.update({"PesoPendiente": 2000, "PesoDespacho": 8000, "Facturado": 10,
            "DespachoFisico": 8, "Pendiente": 2, "UltimoDespacho": "2026-01-02"})
        snapshot = self._snapshot("overview-pie")
        snapshot._prepare(); snapshot._load_next()
        service = self.env["dispatch.dashboard"]
        filters = {"source_id": self.source.id, "date_from": "2026-01-01", "date_to": "2026-01-01"}
        result = service.get_data(filters)
        self.assertEqual(result["agreements"]["groups"][0]["key"], "calendar:2")
        self.assertEqual(result["agreements"]["groups"][0]["pending_tons"], 2)
        self.assertEqual([p["pct"] for p in result["dispatch_progress"]["tons"]["series"]], [80, 20])
        action = service.get_detail_action(filters, "agreement", "calendar:2")
        self.assertIn(("id", "in", snapshot.invoice_ids.ids), action["domain"])
