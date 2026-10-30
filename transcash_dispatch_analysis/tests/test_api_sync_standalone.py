"""GET, feed-contract and sync control-flow checks without a live Odoo server."""
from datetime import date, datetime
import json
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from test_import_queue_standalone import load_model, Cursor, Job

sync = load_model("api_sync")
http = load_model("api_administrator")
from dispatch_queue_test.services import api_import as adapter
from dispatch_queue_test.services.engine import aggregate_invoice, iter_invoice_groups, unique_invoice_lines, latest_invoice_versions

TODAY = date(2026, 10, 29)


def line(**changes):
    return dict({"TipoFactura": "FA", "NumeroFactura": "0001", "FechaFactura": "2026-10-20",
        "Ciudad": "Guayaquil", "Cond_Entrega": "Entrega Transcash", "CodBodega": "B1",
        "CodProducto": "P1", "Facturado": 10, "DespachoFisico": 0, "AjusteDevolucion": 0,
        "Pendiente": 10, "PesoPendiente": 10000, "PesoDespacho": 0, "PalletsPendientes": 5}, **changes)


class ContractTests(unittest.TestCase):
    def convert(self, raw): return adapter.convert_dispatch_payload(raw, TODAY)

    def test_flat_and_wrapped_responses(self):
        for raw in ([line()], {"data": [line()]}, {"success": True, "result": {"rows": [line()]}}, json.dumps([line()]), line()):
            with self.subTest(raw=type(raw)):
                result = self.convert(raw)
                self.assertEqual(result["cutoff_date"], "2026-10-29")
                self.assertEqual(result["rows"][0]["NumeroFactura"], "0001")

    def test_sql_column_case_and_underscores(self):
        raw = {"tipo": " fa ", "numero": " 001 ", "fecha_factura": "2026-10-01T12:00:00",
               "despacho_fisico": 3, "facturado": "10", "pendiente": "7", "peso_pendiente": "7000,5"}
        row = self.convert([raw])["rows"][0]
        self.assertEqual((row["TipoFactura"], row["NumeroFactura"], row["PesoPendiente"]), ("FA", "001", 7000.5))
        self.assertEqual(row["FechaFactura"], "2026-10-01")

    def test_optional_weights_and_pallets_stay_unknown(self):
        raw = line(); del raw["PalletsPendientes"]; del raw["PesoPendiente"]
        row = self.convert([raw])["rows"][0]
        self.assertNotIn("PalletsFacturados", row)
        self.assertNotIn("PalletsPendientes", row)
        self.assertNotIn("PesoPendiente", row)

    def test_dates_are_localized_before_reducing_timestamps(self):
        row = self.convert([line(FechaFactura="2026-10-02T02:00:00Z", UltimoDespacho="2026-10-03T09:00:00-05:00")])["rows"][0]
        self.assertEqual(row["FechaFactura"], "2026-10-01")
        self.assertEqual(row["UltimoDespacho"], "2026-10-03")

    def test_declared_cutoff_and_future_guard(self):
        self.assertEqual(self.convert({"fecha_corte": "2026-10-28", "data": [line()]})["cutoff_date"], "2026-10-28")
        with self.assertRaises(adapter.DispatchAPIError): self.convert({"fecha_corte": "2026-10-30", "data": [line()]})

    def test_empty_error_and_metadata_only_do_not_replace_data(self):
        for raw in ([], {"data": []}, {"success": False, "data": [line()]}, {"error": "SECRET"}, {}, "not json", 10):
            with self.subTest(raw=raw), self.assertRaises(adapter.DispatchAPIError) as caught: self.convert(raw)
            self.assertNotIn("SECRET", str(caught.exception))

    def test_partial_pages_and_controls_are_rejected(self):
        for metadata in ({"has_more": True}, {"next_page": 2}, {"total_rows": 2}, {"total": 2},
                         {"links": {"next": "/secret"}}, {"pagination": {"total_pages": 3}}, {"last_page": 4}):
            with self.subTest(metadata=metadata), self.assertRaises(adapter.DispatchAPIError):
                self.convert({**metadata, "data": [line()]})
        self.assertEqual(len(self.convert({"total_rows": 1, "data": [line()]})["rows"]), 1)

    def test_conflicting_metadata_rejected(self):
        for raw in ({"fecha_corte": "2026-10-28", "data": {"cutoff_date": "2026-10-29", "rows": [line()]}},
                    {"total_rows": 1, "data": {"total_rows": 2, "rows": [line()]}}):
            with self.assertRaises(adapter.DispatchAPIError): self.convert(raw)

    def test_bad_keys_and_numbers_report_line_without_raw_data(self):
        for changes in ({"NumeroFactura": None}, {"NumeroFactura": 1.2}, {"TipoFactura": True},
                        {"Facturado": "SECRET"}, {"Pendiente": float("nan")}, {"PesoPendiente": True}):
            with self.subTest(changes=changes), self.assertRaises(adapter.DispatchAPIError) as caught:
                self.convert([line(**changes)])
            self.assertNotIn("SECRET", str(caught.exception))

    def test_required_quantities_and_date_format(self):
        raw = line(); del raw["DespachoFisico"]
        with self.assertRaises(adapter.DispatchAPIError): self.convert([raw])
        with self.assertRaises(adapter.DispatchAPIError): self.convert([line(FechaFactura="29/10/2026")])

    def test_equivalent_columns_cannot_disagree(self):
        with self.assertRaises(adapter.DispatchAPIError): self.convert([dict(line(), peso_pendiente=7)])

    def test_last_duplicate_updates_pending_instead_of_adding(self):
        result = self.convert([line(), line(DespachoFisico=6, Pendiente=4, PesoPendiente=4000, PesoDespacho=6000)])
        key, rows = next(iter_invoice_groups(result["rows"]))
        unique, removed, changed = unique_invoice_lines(rows)
        invoice = aggregate_invoice(key, unique, TODAY)
        self.assertEqual((removed, changed, result["unique_lines"]), (1, 1, 1))
        self.assertEqual(invoice["pending_weight"], 4000)

    def test_details_and_invoice_types_are_kept(self):
        result = self.convert([line(), line(CodBodega="B2"), line(CodProducto="P2"), line(TipoFactura="NC")])
        self.assertEqual(result["unique_lines"], 4)
        self.assertEqual(len(list(iter_invoice_groups(result["rows"]))), 2)

    def test_named_warehouses_do_not_collapse_when_code_is_absent(self):
        rows = [dict(line(CodBodega=None), Bodega=name) for name in ("Norte", "Sur")]
        result = self.convert(rows)
        self.assertEqual(result["unique_lines"], 2)

    def test_checksum_ignores_record_order_but_respects_duplicate_update_order(self):
        a, b = line(), line(NumeroFactura="0002")
        self.assertEqual(self.convert([a, b])["checksum"], self.convert([b, a])["checksum"])
        changed = line(Pendiente=4, DespachoFisico=6, PesoPendiente=4000)
        self.assertNotEqual(self.convert([a, changed])["checksum"], self.convert([changed, a])["checksum"])
        self.assertEqual(self.convert([a, a])["checksum"], self.convert([a])["checksum"])

    def test_row_limit(self):
        with patch.object(adapter, "MAX_ROWS", 1), self.assertRaises(adapter.DispatchAPIError):
            self.convert([line(), line(NumeroFactura="2")])

    def test_chunk_row_and_byte_limits(self):
        self.assertEqual([len(c) for c in adapter.iter_api_chunks([line()] * 5001)], [5000, 1])
        size = len(json.dumps(line(), ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode())
        with patch.object(adapter, "MAX_CHUNK_BYTES", size * 2):
            self.assertEqual([len(c) for c in adapter.iter_api_chunks([line()] * 3)], [1, 1, 1])
        with patch.object(adapter, "MAX_CHUNK_BYTES", 10), self.assertRaises(adapter.DispatchAPIError):
            list(adapter.iter_api_chunks([line()]))


class AdminLookup:
    def __init__(self, records): self.records = records; self.domain = None
    def sudo(self): return self
    def with_company(self, company): self.company = company; return self
    def search(self, domain, **kwargs): self.domain = domain; return self.records


class FetchTests(unittest.TestCase):
    def env(self, records):
        admin = AdminLookup(records)
        class Env:
            registry = {"api.administrator": True}
            company = SimpleNamespace(id=7)
            def __getitem__(self, name): return admin
        return Env(), admin

    def test_exact_endpoint_active_get_and_company(self):
        env, admin = self.env([SimpleNamespace(call_dispatch_api=lambda: [line()])])
        self.assertEqual(adapter.fetch_dispatch_api(env), [line()])
        self.assertEqual(admin.domain, [("name", "=", "getdatosdespachos"), ("type", "=", "get"),
                                       ("status", "=", "A"), ("company_id", "=", 7)])

    def test_missing_and_multiple_configs_are_rejected(self):
        for records in ([], [object(), object()]):
            with self.assertRaises(adapter.DispatchAPIError): adapter.fetch_dispatch_api(self.env(records)[0])

    def test_missing_addon(self):
        with self.assertRaises(adapter.DispatchAPIError): adapter.fetch_dispatch_api(SimpleNamespace(registry={}))


class Response:
    status_code = 200
    def __init__(self, payload=b'[]'): self.payload = payload; self.closed = False
    def iter_content(self, **kwargs): yield self.payload
    def close(self): self.closed = True
    def raise_for_status(self): pass


class TransportTests(unittest.TestCase):
    def record(self):
        company = SimpleNamespace(id=1)
        return SimpleNamespace(ensure_one=lambda:None, check_access_rights=lambda *a:None,
            check_access_rule=lambda *a:None, company_id=company, name="getdatosdespachos", type="get", status="A",
            url="https://erp.invalid/api/", end_point="/getdatosdespachos", user_id="api-user", password="api-secret",
            env=SimpleNamespace(company=company, su=True))

    def test_get_headers_and_credentials_stay_in_server_request(self):
        response = Response(b'{"data": []}')
        with patch.object(http.requests, "get", return_value=response) as get:
            self.assertEqual(http.APIAdministrator.call_dispatch_api(self.record()), {"data": []})
        args, kwargs = get.call_args
        self.assertEqual(args, ("https://erp.invalid/api/getdatosdespachos",))
        self.assertEqual(kwargs["headers"], {"Accept":"application/json", "version":"1", "framework":"PRUEBAS",
            "userid":"api-user", "password":"api-secret", "deviceid":"000000000000000", "sessionid":"0"})
        self.assertEqual(kwargs["timeout"], (10, 120))
        self.assertFalse(kwargs["allow_redirects"])
        self.assertTrue(response.closed)

    def test_redirect_and_bad_json_are_closed(self):
        for response in (Response(b'not json'), Response()):
            if response.payload == b'[]': response.status_code = 302
            with patch.object(http.requests, "get", return_value=response), self.assertRaises(http.UserError):
                http.APIAdministrator.call_dispatch_api(self.record())
            self.assertTrue(response.closed)

    def test_timeout_and_http_error_never_echo_url_credentials_or_body(self):
        for error in (http.requests.Timeout("api-secret"), http.requests.HTTPError("api-secret https://private.invalid")):
            with patch.object(http.requests, "get", side_effect=error), self.assertRaises(http.UserError) as caught:
                http.APIAdministrator.call_dispatch_api(self.record())
            self.assertNotIn("api-secret", str(caught.exception)); self.assertNotIn("private.invalid", str(caught.exception))

    def test_body_size_limit(self):
        response = Response(b"123456")
        with patch.object(http, "MAX_RESPONSE_BYTES", 5), patch.object(http.requests, "get", return_value=response), self.assertRaises(http.UserError):
            http.APIAdministrator.call_dispatch_api(self.record())
        self.assertTrue(response.closed)

    def test_invalid_company_config_url_and_credentials_do_not_send_request(self):
        for changes in ({"company_id":SimpleNamespace(id=2)}, {"name":"other"}, {"status":"I"}, {"type":"post"},
                        {"url":"file:///etc/passwd", "end_point":""}, {"url":"https://u:p@example.invalid", "end_point":""}, {"password":""}):
            record = self.record(); record.__dict__.update(changes)
            with patch.object(http.requests, "get") as get, self.assertRaises(http.UserError):
                http.APIAdministrator.call_dispatch_api(record)
            get.assert_not_called()

    def test_unprivileged_rpc_cannot_fetch(self):
        record = self.record(); record.env.su = False; record.env.user = SimpleNamespace(has_group=lambda group:False)
        with self.assertRaises(http.AccessError): http.APIAdministrator.call_dispatch_api(record)


class PullSnapshot:
    def __init__(self, values, identity):
        self.__dict__.update(values); self.id = identity; self.chunks = []; self.state = values["state"]
    def api_append_chunk(self, index, rows): self.chunks.append(rows)
    def api_finalize(self, chunks, rows):
        assert chunks == len(self.chunks) and rows == sum(map(len, self.chunks))
        self.total_rows = rows; self.state = "queued"
    def action_open_progress(self): return {"type":"ir.actions.client", "tag":"transcash_dispatch_import_progress", "params":{"snapshot_id":self.id}}


class Snapshots:
    def __init__(self): self.rows = []
    def search(self, domain, **kwargs):
        return next((r for r in self.rows if r.state in ("receiving", "queued", "loading")), False)
    def create(self, values):
        result = PullSnapshot(values, len(self.rows) + 1); self.rows.append(result); return result
    def browse(self, identity): return next(r for r in self.rows if r.id == identity)


class Source:
    _sync_dispatch_api = sync.DispatchSourceAPI._sync_dispatch_api
    action_sync_api = sync.DispatchSourceAPI.action_sync_api
    def __init__(self):
        self.id = 3; self.name = "ERP"; self.active = True; self.active_snapshot_id = False
        self.company_id = SimpleNamespace(id=1, partner_id=SimpleNamespace(tz="America/Guayaquil"))
        self.snapshots = Snapshots()
        owner = self
        class Env:
            cr = Cursor()
            def __getitem__(self, name): return owner.snapshots
        self.env = Env(); self.api_last_message = ""; self.api_last_auto_at = False
    def ensure_one(self): pass
    def invalidate_recordset(self): pass
    def with_context(self, **kwargs): return self
    def sudo(self): return self
    def with_company(self, company): return self
    def _check_operator(self): pass
    def write(self, values): self.__dict__.update(values)
    def pull(self, raw):
        with patch.object(sync, "fetch_dispatch_api", return_value=raw): return self._sync_dispatch_api()
    def finish(self, snapshot):
        if self.active_snapshot_id: self.active_snapshot_id.state = "archived"
        snapshot.state = "ready"; self.active_snapshot_id = snapshot


class SyncTests(unittest.TestCase):
    def test_repeat_while_queued_and_unchanged_after_publish_do_not_create_duplicates(self):
        source = Source(); first = source.pull([line()])
        with patch.object(sync, "fetch_dispatch_api") as fetch:
            self.assertEqual(source._sync_dispatch_api()["snapshot_id"], first["snapshot_id"]); fetch.assert_not_called()
        source.finish(source.snapshots.rows[0])
        self.assertTrue(source.pull([line()])["unchanged"])
        self.assertEqual(len(source.snapshots.rows), 1)

    def test_updates_and_reversion_create_new_current_version(self):
        source = Source(); source.pull([line()]); source.finish(source.snapshots.rows[0])
        changed = line(DespachoFisico=6, Pendiente=4, PesoPendiente=4000, PesoDespacho=6000)
        source.pull([changed]); source.finish(source.snapshots.rows[1])
        source.pull([line()]); source.finish(source.snapshots.rows[2])
        self.assertEqual(len(source.snapshots.rows), 3)
        versions = [{"id":r.id,"company_id":1,"invoice_type":"FA","internal_number":"0001",
                     "cutoff_date":r.cutoff_date,"snapshot_id":r.id} for r in source.snapshots.rows]
        self.assertEqual(latest_invoice_versions(versions), [3])

    def test_old_api_cutoff_and_empty_response_keep_active_version(self):
        source = Source(); source.pull([line()]); source.finish(source.snapshots.rows[0])
        for raw in ([], {"fecha_corte":"2026-10-28","data":[line()]}):
            self.assertTrue(source.pull(raw)["error"])
            self.assertEqual(source.active_snapshot_id.id, 1)
        self.assertEqual(len(source.snapshots.rows), 1)

    def test_source_lock_prevents_http_overlap(self):
        source = Source(); source.env.cr.lock = False
        with patch.object(sync, "fetch_dispatch_api") as fetch:
            self.assertNotIn("snapshot_id", source._sync_dispatch_api()); fetch.assert_not_called()

    def test_generic_errors_are_redacted_and_preserve_current(self):
        source = Source()
        with patch.object(sync, "fetch_dispatch_api", side_effect=RuntimeError("api-secret")):
            result = source._sync_dispatch_api()
        self.assertTrue(result["error"]); self.assertNotIn("api-secret", result["message"])

    def test_manual_access_is_checked_before_elevation_or_http(self):
        source = Source()
        def denied(): raise PermissionError()
        source._check_operator = denied
        with patch.object(sync, "fetch_dispatch_api") as fetch, self.assertRaises(PermissionError):
            source.action_sync_api()
        fetch.assert_not_called()

    def test_manual_action_returns_complete_progress_contract(self):
        source = Source()
        with patch.object(sync, "fetch_dispatch_api", return_value=[line()]): action = source.action_sync_api()
        self.assertEqual(action["tag"], "transcash_dispatch_import_progress")
        self.assertEqual(action["params"]["snapshot_id"], 1)

    def test_api_rows_use_existing_city_policy_and_invoice_pipeline(self):
        dataset = adapter.convert_dispatch_payload([line(), line(CodBodega="B2", Ciudad="Guayaquil"),
            line(NumeroFactura="0002", Ciudad="Cuenca"), line(NumeroFactura="0002", Ciudad="Cuenca")], TODAY)
        job = Job(); job.company_id.partner_id = SimpleNamespace(tz="America/Guayaquil")
        job._rows = lambda: iter(dataset["rows"])
        job._prepare(); job._load_next()
        self.assertEqual(job.total_invoices, 2)
        self.assertEqual(job.duplicate_rows, 1)
        self.assertEqual(job.env.invoices.line_count, 3)
        self.assertEqual(job.env.invoices.sla_days_counts, {"GUAYAQUIL":{3}, "CUENCA":{9}})


class CronSources:
    _cron_sync_dispatch_api = sync.DispatchSourceAPI._cron_sync_dispatch_api
    def __init__(self, rows):
        self.rows = rows; self.notifications = []
        owner = self
        class Env:
            cr = Cursor()
            def __getitem__(self, name): return SimpleNamespace(_notify_progress=lambda **kw:owner.notifications.append(kw))
        self.env = Env()
    def sudo(self): return self
    def eligible(self, domain):
        cycle = next(term[2] for term in domain if isinstance(term, tuple) and term[:2] == ("api_last_auto_at", "<"))
        return [r for r in self.rows if r.active and getattr(r, "api_sync_enabled", False)
                and (not r.api_last_auto_at or r.api_last_auto_at < cycle)]
    def search(self, domain, **kwargs): return next(iter(self.eligible(domain)), False)
    def search_count(self, domain): return len(self.eligible(domain))


class CronTests(unittest.TestCase):
    def test_two_hour_cycle_batches_each_enabled_source_once_and_uses_its_company(self):
        rows = [Source(), Source(), Source()]
        calls = []
        for identity, source in enumerate(rows, 1):
            source.id = identity; source.api_sync_enabled = identity != 3
            source._sync_dispatch_api = lambda s=source:calls.append(s.company_id.id)
            source.with_company = lambda company, s=source:(calls.append(("company", company.id)) or s)
        rows[1].company_id = SimpleNamespace(id=2)
        cron = CronSources(rows)
        for _ in range(3): cron._cron_sync_dispatch_api()
        self.assertEqual(calls, [("company",1),1,("company",2),2])
        self.assertEqual(cron.notifications[:2], [{"done":1,"remaining":1},{"done":1,"remaining":0}])
        self.assertFalse(rows[2].api_last_auto_at)
        rows[0].api_last_auto_at = datetime(2026,10,29,15,0)
        cron._cron_sync_dispatch_api()
        self.assertEqual(calls[-1], 1)

    def test_busy_source_does_not_fetch_or_mark_a_finished_cycle(self):
        source = Source(); source.api_sync_enabled = True
        cron = CronSources([source]); cron.env.cr.lock = False
        with patch.object(source, "_sync_dispatch_api") as run:
            cron._cron_sync_dispatch_api(); run.assert_not_called()
        self.assertFalse(source.api_last_auto_at)

    def test_error_from_api_is_recorded_and_not_retried_repeatedly_in_same_cycle(self):
        source = Source(); source.api_sync_enabled = True
        cron = CronSources([source])
        with patch.object(sync, "fetch_dispatch_api", side_effect=adapter.DispatchAPIError("Servicio no disponible")) as fetch:
            cron._cron_sync_dispatch_api(); cron._cron_sync_dispatch_api()
        self.assertEqual(fetch.call_count, 1)
        self.assertEqual(source.api_last_result, "error")

    def test_schedule_is_two_hours_and_preserves_import_queue(self):
        import xml.etree.ElementTree as ET
        from test_import_queue_standalone import ROOT
        record = ET.parse(ROOT/"data/api_cron.xml").find(".//record")
        fields = {f.get("name"):f.text for f in record.findall("field")}
        self.assertEqual((fields["interval_number"],fields["interval_type"]), ("2","hours"))
        self.assertEqual(fields["code"], "model._cron_sync_dispatch_api()")
        self.assertIn("model._cron_process()", (ROOT/"data/cron.xml").read_text())


if __name__ == "__main__": unittest.main()
