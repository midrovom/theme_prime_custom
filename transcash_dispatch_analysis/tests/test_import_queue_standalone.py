"""Control-flow regression tests using the real model methods and a fake ORM.

These run without an Odoo/PostgreSQL service. They do not claim to validate SQL
transactions or Odoo ACL enforcement; native integration tests cover that path.
"""
from contextlib import contextmanager
from datetime import date, datetime
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import ModuleType, SimpleNamespace
import ast
import base64
import json
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]


class Field:
    def __call__(self, *args, **kwargs): return None
    @staticmethod
    def now(): return datetime(2026, 10, 29, 18, 0)
    @staticmethod
    def context_today(*args): return date(2026, 10, 29)
    @staticmethod
    def create(value): return (0, 0, value)


class FakeAccessError(Exception): pass


def load_model(model_name="snapshot"):
    saved = {name: sys.modules.get(name) for name in ("odoo", "odoo.exceptions", "odoo.tools", "odoo.tools.safe_eval")}
    odoo = ModuleType("odoo")
    odoo.api = SimpleNamespace(model=lambda f: f, model_create_multi=lambda f: f,
        depends=lambda *a: lambda f: f, constrains=lambda *a: lambda f: f, onchange=lambda *a: lambda f: f)
    odoo.fields = SimpleNamespace(**{n: Field() for n in ("Char", "Many2one", "Many2many", "One2many", "Date", "Datetime", "Selection", "Binary", "Json", "Text", "Integer", "Float", "Boolean", "Command")})
    odoo.models = SimpleNamespace(Model=object, AbstractModel=object)
    odoo._ = lambda s: s
    errors = ModuleType("odoo.exceptions")
    errors.AccessError = FakeAccessError
    errors.UserError = type("UserError", (Exception,), {})
    errors.ValidationError = type("ValidationError", (Exception,), {})
    sys.modules["odoo"] = odoo; sys.modules["odoo.exceptions"] = errors
    safe_module=ModuleType("odoo.tools.safe_eval");safe_module.safe_eval=lambda value,env=None:ast.literal_eval(value)
    sys.modules["odoo.tools"]=ModuleType("odoo.tools");sys.modules["odoo.tools.safe_eval"]=safe_module
    for name, path in (("dispatch_queue_test", ROOT), ("dispatch_queue_test.models", ROOT/"models"), ("dispatch_queue_test.services", ROOT/"services")):
        pkg = ModuleType(name); pkg.__path__ = [str(path)]; sys.modules[name] = pkg
    try:
        spec = spec_from_file_location("dispatch_queue_test.models."+model_name, ROOT/("models/"+model_name+".py"))
        module = module_from_spec(spec); sys.modules[spec.name] = module; spec.loader.exec_module(module)
        return module
    finally:
        for name, value in saved.items():
            if value is None: sys.modules.pop(name, None)
            else: sys.modules[name] = value


module = load_model()
Snapshot = module.DispatchSnapshot
configuration_module = load_model("configuration")


class Company:
    def __init__(self, identity): self.id = identity
    def ensure_one(self): pass


class Sla:
    _ensure_city_defaults = configuration_module.DispatchSla._ensure_city_defaults
    _initialize_city_defaults = configuration_module.DispatchSla._initialize_city_defaults
    _policy_pack = configuration_module.DispatchSla._policy_pack

    def __init__(self, env): self.env = env; self.records = []; self.context = {}
    def sudo(self): return self
    def with_context(self, **kwargs):
        other = Sla(self.env); other.records = self.records; other.context = dict(self.context, **kwargs)
        return other
    def browse(self): return []
    def create(self, values):
        created = []
        for value in values:
            rule = SimpleNamespace(id=len(self.records)+1, company_id=value["company_id"],
                city=value.get("city", ""), city_key=configuration_module.normalize(value.get("city")),
                delivery_key=configuration_module.normalize(value.get("delivery")),
                max_days=value.get("max_days", 9), day_type=value.get("day_type", "calendar"),
                valid_from=value.get("valid_from", date(1900,1,1)), valid_to=value.get("valid_to",False),
                active=value.get("active",True))
            self.records.append(rule); created.append(rule)
        return created
    def search(self, domain):
        result = []
        for rule in self.records:
            if not self.context.get("active_test") is False and not rule.active: continue
            if all((getattr(rule,field) or False) == value for field,op,value in domain if op == "="):
                result.append(rule)
        return result


class Cursor:
    def __init__(self): self.lock = True
    @contextmanager
    def savepoint(self): yield
    def execute(self, query, params): self.params = params
    def fetchone(self): return [self.lock]


class Chunks:
    def __init__(self, env): self.env = env; self.records = []
    def create(self, values):
        chunk = Chunk(self, values); self.records.append(chunk); return chunk
    def search(self, domain, **kwargs):
        rows = [r for r in self.records if all(getattr(r, field) == value for field, op, value in domain if op == "=")]
        return sorted(rows, key=lambda r:r.sequence)[0] if rows else False


class Chunk:
    def __init__(self, owner, values):
        self.owner = owner; self.loaded = False; self.context = {}
        self.__dict__.update(values)
    def with_context(self, **kwargs): self.context.update(kwargs); return self


class ChunkSet:
    def __init__(self, model, records=None): self.model = model; self.records = records
    def current(self): return self.records if self.records is not None else self.model.records
    def __iter__(self): return iter(self.current())
    def filtered(self, fn): return ChunkSet(self.model, [r for r in self.current() if fn(r)])
    def unlink(self):
        for row in list(self.current()): self.model.records.remove(row)


class Invoices:
    def __init__(self):
        self.count = self.line_count = self.pending_count = self.tc_pending_count = 0
        self.created_values = []; self.city_groups = []; self.sla_days_counts = {}
        tree = ast.parse((ROOT/"models/invoice.py").read_text())
        self._fields = {n.targets[0].id:None for c in tree.body if isinstance(c,ast.ClassDef) and c.name=="DispatchInvoice" for n in c.body if isinstance(n,ast.Assign) and isinstance(n.targets[0],ast.Name)}
    def unlink(self): pass
    def _upsert_snapshot_values(self, snapshot, values): self.create(values)
    def _refresh_current_records(self, company_id): self.published_company=company_id
    def create(self, values):
        self.created_values.extend({k:v for k,v in value.items() if k != "line_ids"} for value in values)
        self.count += len(values)
        self.line_count += sum(len(v.get("line_ids",[])) for v in values)
        self.pending_count += sum(bool(v.get("pending")) for v in values)
        self.tc_pending_count += sum(bool(v.get("pending")) and v.get("delivery")=="Entrega Transcash" for v in values)
        for value in values:
            city, days = value.get("city"), value.get("sla_days")
            self.sla_days_counts.setdefault(city,set()).add(days)
    def sudo(self): return self
    def read_group(self, domain, fields, groupby, **kwargs):
        companies = next(value for field,op,value in domain if field=="company_id")
        return [group for group in self.city_groups if group["company_id"][0] in companies]


class Environment:
    def __init__(self):
        self.cr = Cursor(); self.su = False
        self.user = SimpleNamespace(has_group=lambda name:True)
        self.invoices = Invoices(); self.chunks = Chunks(self)
        self.models = {"dispatch.invoice":self.invoices,"dispatch.chunk":self.chunks,
                       "dispatch.sla":Sla(self), "dispatch.holiday":SimpleNamespace(search=lambda domain:[]),
                       "dispatch.warehouse":SimpleNamespace(_ensure_records=lambda company,rows:{})}
    def __getitem__(self,name): return self.models[name]


class Job:
    _progress_payload = Snapshot._progress_payload
    process_import_step = Snapshot.process_import_step
    _run_import_step = Snapshot._run_import_step
    _try_import_lock = Snapshot._try_import_lock
    _rows = Snapshot._rows
    _prepare = Snapshot._prepare
    _store_prepared = Snapshot._store_prepared
    _invoice_values = Snapshot._invoice_values
    _load_next = Snapshot._load_next
    _activate = Snapshot._activate

    def __init__(self):
        self.env = Environment(); self.id = 7; self.state = "queued"
        self.name = "Test import"; self.file_name = "test.xlsx"; self.input_type = "xlsx"
        self.raw_file = False; self.error_message = ""; self.last_progress_at = False
        self.total_invoices = self.loaded_invoices = self.total_rows = 0
        self.policy_pack = {}; self.cutoff_date = date(2026,10,29)
        self.company_id = Company(1)
        self.source_id = SimpleNamespace(id=4,active_snapshot_id=False)
        self.authorized = True; self.sudo_calls = 0; self.context = {}; self.preparations = self.loads = 0
    def ensure_one(self): pass
    def check_access_rights(self, mode): pass
    def check_access_rule(self, mode): pass
    def invalidate_recordset(self): pass
    def _operator(self):
        if not self.authorized: raise FakeAccessError("Not authorized")
    def sudo(self): self.sudo_calls += 1; return self
    def with_context(self, **kwargs): self.context.update(kwargs); return self
    def write(self, values): self.__dict__.update(values)
    @property
    def invoice_ids(self): return self.env.invoices
    @property
    def chunk_ids(self): return ChunkSet(self.env.chunks)


class QueueTests(unittest.TestCase):
    def test_unauthorized_runner_never_elevates(self):
        job=Job();job.authorized=False
        with self.assertRaises(FakeAccessError):job.process_import_step()
        self.assertEqual(job.sudo_calls,0)

    def test_busy_job_does_not_execute_same_block(self):
        job=Job();job.env.cr.lock=False
        job._prepare=lambda:self.fail("Must not prepare a locked job")
        self.assertTrue(job.process_import_step()["busy"])
        self.assertEqual(job.state,"queued")

    def test_interactive_runner_does_not_require_a_cron(self):
        job=Job()
        def prepare(): job.state="loading";job.total_invoices=2;job.total_rows=3
        def load(): job.loaded_invoices+=1;job.state="ready" if job.loaded_invoices==2 else "loading"
        job._prepare=prepare;job._load_next=load
        self.assertEqual(job.process_import_step()["state"],"loading")
        self.assertEqual(job.process_import_step()["loaded_invoices"],1)
        self.assertTrue(job.process_import_step()["done"])
        self.assertEqual(job.context["bin_size"],False)
        self.assertEqual(job.env.cr.params,(180104,4))

    def test_finished_job_is_idempotent(self):
        job=Job();job.state="ready";job.loaded_invoices=job.total_invoices=2
        job._prepare=lambda:self.fail("Cannot prepare a finished import")
        job._load_next=lambda:self.fail("Cannot load a finished import")
        self.assertTrue(job.process_import_step()["done"])

    def test_preparation_failure_is_returned_to_the_screen(self):
        job=Job()
        def fail():raise ValueError("Falta una columna obligatoria")
        job._prepare=fail
        with self.assertLogs(module._logger,level="ERROR"):
            result=job.process_import_step()
        self.assertTrue(result["failed"])
        self.assertIn("columna obligatoria",result["error_message"])

    def test_missing_prepared_block_does_not_loop_forever(self):
        job=Job();job.state="loading";job.loaded_invoices=1;job.total_invoices=2
        with self.assertLogs(module._logger,level="ERROR"):
            result=job.process_import_step()
        self.assertTrue(result["failed"])
        self.assertIn("Faltan bloques",result["error_message"])

    def test_prepared_block_control_is_checked_before_create(self):
        job=Job();job.state="loading";job.total_invoices=2
        job.env.chunks.create({"snapshot_id":7,"phase":"prepared","sequence":0,"row_count":2,"payload":base64.b64encode(b'[{}]')})
        with self.assertLogs(module._logger,level="ERROR"):result=job.process_import_step()
        self.assertTrue(result["failed"]);self.assertEqual(job.env.invoices.count,0)

    def test_last_block_activates_only_after_creation(self):
        job=Job();job.state="loading";job.total_invoices=1;job.total_rows=1
        job._invoice_values=lambda item,warehouse_map=None:{"line_ids":[(0,0,{})]}
        chunk=job.env.chunks.create({"snapshot_id":7,"phase":"prepared","sequence":0,"row_count":1,"payload":base64.b64encode(b'[{"lines":[]}]')})
        result=job.process_import_step()
        self.assertTrue(result["done"]);self.assertEqual(job.env.invoices.count,1)
        self.assertEqual(job.source_id.active_snapshot_id,job)
        self.assertEqual(chunk.context,{"bin_size":False})
        self.assertFalse(job.env.chunks.records)

    def test_cron_notify_failure_does_not_escape_successful_step(self):
        job=Job()
        def prepare():job.state="loading"
        job._prepare=prepare
        def broken_notify(**kwargs):raise RuntimeError("notify is unavailable")
        job.env.models["ir.cron"]=SimpleNamespace(_notify_progress=broken_notify)
        runner=SimpleNamespace(env=job.env,search=lambda *a,**k:[job],search_count=lambda *a,**k:1)
        with self.assertLogs(module._logger,level="WARNING"):Snapshot._cron_process(runner)
        self.assertEqual(job.state,"loading")

    def test_cron_skips_busy_job_and_processes_next(self):
        busy, free=Job(),Job();busy.env.cr.lock=False
        free._prepare=lambda:free.write({"state":"loading"})
        free.env.models["ir.cron"]=SimpleNamespace()
        runner=SimpleNamespace(env=free.env,search=lambda *a,**k:[busy,free],search_count=lambda *a,**k:1)
        Snapshot._cron_process(runner)
        self.assertEqual(busy.state,"queued");self.assertEqual(free.state,"loading")

    def test_progress_is_not_success_before_final_activation(self):
        values=module.progress_values("loading",10,10,12)
        self.assertFalse(values["done"]);self.assertLess(values["progress_percent"],100)
        self.assertEqual(module.progress_values("ready",10,10,12)["progress_percent"],100)


if __name__=="__main__":unittest.main()
