"""Read-only. Execute inside an administrator Odoo shell with its `env`."""
import inspect
from pprint import pprint
from odoo import fields, tools
from odoo.modules.module import get_module_path

print("Módulo y carpeta cargados:")
print(get_module_path("transcash_dispatch_analysis"))
module = env["ir.module.module"].sudo().search([("name", "=", "transcash_dispatch_analysis")])
pprint(module.read([name for name in ("name", "state", "installed_version", "latest_version") if name in module._fields]))
try:
    source = inspect.getsource(type(env["dispatch.snapshot"])._cron_process)
    print("Procesamiento de varios bloques por ejecución:", "CRON_MAX_STEPS" in source)
    print("Solicitud de continuación al terminar:", "_schedule_import" in source)
except (OSError, TypeError):
    print("No se pudo inspeccionar el código cargado; revisar la carpeta y el reinicio de todos los trabajadores.")

print("Configuración de trabajadores de ESTE proceso (puede haber otro proceso dedicado a cron):")
for name in ("workers", "max_cron_threads", "limit_time_cpu", "limit_time_real", "limit_time_real_cron"):
    try:
        print(name, tools.config[name])
    except KeyError:
        pass

print("Cron de carga:")
cron = env.ref("transcash_dispatch_analysis.cron_dispatch_import", raise_if_not_found=False)
if cron:
    cron = cron.sudo()
    pprint(cron.read([name for name in ("active", "nextcall", "lastcall", "failure_count", "first_failure_date", "interval_number", "interval_type") if name in cron._fields]))
    if "ir.cron.trigger" in env.registry:
        triggers = env["ir.cron.trigger"].sudo()
        print("Solicitudes de ejecución guardadas:", triggers.search_count([("cron_id", "=", cron.id)]))
        pprint(triggers.search([("cron_id", "=", cron.id)], order="call_at desc", limit=5).read(["call_at"]))

print("Últimas diez cargas y tiempos observados:")
now = fields.Datetime.to_datetime(fields.Datetime.now())
snapshots = env["dispatch.snapshot"].sudo().search([], order="id desc", limit=10)
names = [name for name in ("name", "source_id", "company_id", "input_type", "state", "total_rows", "total_invoices", "loaded_invoices", "started_at", "finished_at", "last_progress_at", "last_step_seconds", "background_batch_size", "api_grouped_rows", "error_message") if name in snapshots._fields]
for values in snapshots.read(names):
    last = fields.Datetime.to_datetime(values.get("last_progress_at"))
    start = fields.Datetime.to_datetime(values.get("started_at"))
    finish = fields.Datetime.to_datetime(values.get("finished_at"))
    if last and values["state"] in ("queued", "loading"):
        values["seconds_since_last_progress"] = round((now - last).total_seconds(), 1)
    if start:
        elapsed = ((finish or now) - start).total_seconds()
        values["elapsed_seconds_including_waits"] = round(elapsed, 1)
        if elapsed > 0:
            values["invoices_per_second_including_waits"] = round(values["loaded_invoices"] / elapsed, 2)
    pprint(values)
print("No se modificaron datos ni se iniciaron importaciones. Los tiempos no incluyen la descarga previa del ERP.")
