"""Run in the destination Odoo test database with api_administrator installed."""
from unittest.mock import patch

from odoo.tests import TransactionCase, tagged
from odoo.exceptions import AccessError, ValidationError
from ..models import api_sync, snapshot as snapshot_model


@tagged("post_install", "-at_install")
class TestDispatchAPISync(TransactionCase):
    def setUp(self):
        super().setUp()
        self.source = self.env["dispatch.source"].create({"name": "API test", "code": "API-TEST"})
        self.row = {"TipoFactura":"FA", "NumeroFactura":"0001", "FechaFactura":"2026-01-01",
                    "Ciudad":"Cuenca", "CodBodega":"B1", "CodProducto":"P1", "Facturado":10,
                    "DespachoFisico":0, "AjusteDevolucion":0, "Pendiente":10,
                    "PesoPendiente":10000, "PesoDespacho":0, "PalletsPendientes":5}

    def pull(self, rows):
        with patch.object(api_sync, "fetch_dispatch_api", return_value={"fecha_corte":"2026-01-10", "data":rows}) as fetch:
            result = self.source._sync_dispatch_api()
        return result, fetch.call_count

    def finish(self, result):
        snapshot = self.env["dispatch.snapshot"].browse(result["snapshot_id"])
        for _ in range(10):
            if snapshot.state in ("ready", "archived", "error"): break
            snapshot._run_import_step()
        self.assertEqual(snapshot.state, "ready", snapshot.error_message)
        return snapshot

    def current(self):
        return self.env["dispatch.invoice"].search([("company_id","=",self.env.company.id),
            ("invoice_type","=","FA"), ("internal_number","=","0001"), ("is_current","=",True)])

    def test_same_api_response_creates_one_operational_invoice_and_no_extra_batch(self):
        first, calls = self.pull([self.row]); snapshot = self.finish(first)
        second, calls = self.pull([self.row])
        self.assertTrue(second["unchanged"])
        self.assertEqual(second["snapshot_id"], snapshot.id)
        self.assertEqual(len(self.current()), 1)
        self.assertEqual(self.env["dispatch.snapshot"].search_count([("source_id","=",self.source.id)]), 1)

    def test_regional_and_php_dates_store_canonical_dates_in_invoice_and_detail(self):
        row = dict(self.row, FechaFactura="05/01/2026 0:00:00", UltimoDespacho={
            "date":"2026-01-08 09:13:24.000000", "timezone_type":3,"timezone":"America/Guayaquil"})
        result, _ = self.pull([row])
        snapshot = self.finish(result)
        self.assertEqual(str(snapshot.invoice_ids.invoice_date), "2026-01-05")
        self.assertEqual(str(snapshot.invoice_ids.line_ids.last_dispatch_date), "2026-01-08")
        self.assertEqual(str(snapshot.invoice_ids.deadline), "2026-01-14")

    def test_changed_pending_replaces_current_and_keeps_detail_history(self):
        first = self.finish(self.pull([self.row])[0])
        changed = dict(self.row, DespachoFisico=6, Pendiente=4, PesoPendiente=4000, PesoDespacho=6000, UltimoDespacho="2026-01-08")
        second = self.finish(self.pull([changed])[0])
        self.assertEqual(first.state, "archived")
        self.assertEqual(first.invoice_ids.pending_weight, 10000)
        self.assertEqual(second.invoice_ids.pending_weight, 4000)
        self.assertEqual(self.current(), second.invoice_ids)
        self.assertEqual(len(self.current()), 1)

    def test_closed_invoice_updates_totals_without_adding_a_second_pending(self):
        self.finish(self.pull([self.row])[0])
        closed = dict(self.row, DespachoFisico=10, Pendiente=0, PesoPendiente=0, PesoDespacho=10000,
                      PalletsPendientes=0, UltimoDespacho="2026-01-08")
        self.finish(self.pull([closed])[0])
        self.assertEqual(len(self.current()), 1)
        self.assertFalse(self.current().pending)
        self.assertEqual(self.current().pending_weight, 0)

    def test_distinct_bodegas_are_preserved_repeated_details_are_replaced(self):
        changed = dict(self.row, DespachoFisico=6, Pendiente=4, PesoPendiente=4000, PesoDespacho=6000)
        snapshot = self.finish(self.pull([self.row, changed, dict(self.row, CodBodega="B2")])[0])
        self.assertEqual(len(snapshot.invoice_ids), 1)
        self.assertEqual(len(snapshot.invoice_ids.line_ids), 2)
        self.assertEqual(snapshot.invoice_ids.pending_weight, 14000)
        self.assertEqual(snapshot.duplicate_rows, 1)

    def test_api_city_defaults_preserve_edited_rules(self):
        first = self.finish(self.pull([self.row])[0])
        self.assertEqual(first.invoice_ids.sla_days, 9)
        rule = self.env["dispatch.sla"].search([("company_id","=",self.env.company.id),("city_key","=","CUENCA"),("delivery_key","=",False)])
        rule.max_days = 14
        second = self.finish(self.pull([dict(self.row, PesoPendiente=9000)])[0])
        self.assertEqual(second.invoice_ids.sla_days, 14)
        self.assertEqual(first.invoice_ids.sla_days, 9)

    def test_inflight_batch_is_reused_without_calling_erp_again(self):
        first, count = self.pull([self.row])
        second, count = self.pull([self.row])
        self.assertEqual(count, 0)
        self.assertEqual(first["snapshot_id"], second["snapshot_id"])

    def test_empty_or_partial_result_keeps_active_data(self):
        snapshot = self.finish(self.pull([self.row])[0])
        result, _ = self.pull([])
        self.assertTrue(result["error"])
        self.assertEqual(self.source.active_snapshot_id, snapshot)
        self.assertEqual(len(self.current()), 1)

    def test_failed_chunk_rolls_back_new_batch_and_keeps_previous_current(self):
        snapshot = self.finish(self.pull([self.row])[0])
        def fail(*args, **kwargs):
            raise ValidationError("Fallo de prueba al recibir bloque")
        with patch.object(snapshot_model.DispatchSnapshot, "api_append_chunk", fail):
            result, _ = self.pull([dict(self.row, PesoPendiente=9000)])
        self.assertTrue(result["error"])
        self.assertEqual(self.source.active_snapshot_id, snapshot)
        self.assertEqual(self.env["dispatch.snapshot"].search_count([("source_id","=",self.source.id)]), 1)
        self.assertEqual(self.current().pending_weight, 10000)

    def test_reader_cannot_start_api_sync(self):
        user = self.env["res.users"].create({"name":"API reader", "login":"dispatch_api_reader_test",
            "company_id":self.env.company.id, "company_ids":[(6,0,[self.env.company.id])],
            "groups_id":[(6,0,[self.env.ref("transcash_dispatch_analysis.group_dispatch_user").id])]})
        with patch.object(api_sync, "fetch_dispatch_api") as fetch, self.assertRaises(AccessError):
            self.source.with_user(user).action_sync_api()
        fetch.assert_not_called()

    def test_only_one_auto_source_per_company(self):
        # Existing configuration is isolated by this test transaction.
        self.env["dispatch.source"].search([("company_id","=",self.env.company.id)]).write({"api_sync_enabled":False})
        self.source.api_sync_enabled = True
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            self.env["dispatch.source"].create({"name":"Duplicate API", "code":"API-TEST-OTHER", "api_sync_enabled":True})
