"""Read-only: run inside the administrator's Odoo shell, using its `env`."""
from pprint import pprint
from odoo.modules.module import get_module_path

print("Carpeta que utiliza Odoo:")
print(get_module_path("transcash_dispatch_analysis"))
modules = env["ir.module.module"].sudo().search([("name", "=", "transcash_dispatch_analysis")])
pprint(modules.read([name for name in ("name", "state", "installed_version", "latest_version") if name in modules._fields]))

print("Cron de procesamiento:")
cron = env.ref("transcash_dispatch_analysis.cron_dispatch_import", raise_if_not_found=False)
if cron:
    pprint(cron.sudo().read([name for name in ("active", "interval_number", "interval_type", "nextcall", "lastcall") if name in cron._fields]))

print("Últimas cargas sin terminar:")
snapshots = env["dispatch.snapshot"].sudo().search([("state", "in", ["receiving", "queued", "loading", "error"])], order="id desc", limit=10)
pprint(snapshots.read(["name", "company_id", "source_id", "input_type", "state", "total_rows", "total_invoices", "loaded_invoices", "last_progress_at", "error_message"]))
print("Este diagnóstico no modifica registros ni inicia importaciones.")
