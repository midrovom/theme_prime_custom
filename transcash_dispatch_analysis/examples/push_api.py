#!/usr/bin/env python3
"""Send a COMPLETE export to Odoo 18 through its authenticated external API.

Input: JSON array of rows or JSONL, matching the exporter's column names.
Set ODOO_URL, ODOO_DB, ODOO_LOGIN, ODOO_API_KEY in the process environment.
No credentials are written to disk. Run from your integration scheduler.
"""
import argparse
import json
import os
import ssl
import xmlrpc.client
from pathlib import Path


def rows(path):
    with path.open(encoding="utf-8") as stream:
        if path.suffix.lower() == ".jsonl":
            for line in stream:
                if line.strip(): yield json.loads(line)
        else:
            yield from json.load(stream)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("file", type=Path)
    parser.add_argument("--source-code", default="TRANSCASH")
    parser.add_argument("--company-id", required=True, type=int)
    parser.add_argument("--cutoff", required=True, help="YYYY-MM-DD, source extraction date")
    parser.add_argument("--batch-key", required=True, help="Stable unique ID for this export; reuse on retries")
    parser.add_argument("--chunk-size", type=int, default=2000)
    args = parser.parse_args()
    if not 1 <= args.chunk_size <= 5000: parser.error("chunk-size debe estar entre 1 y 5.000")
    url, db, login, key = (os.environ[n] for n in ("ODOO_URL", "ODOO_DB", "ODOO_LOGIN", "ODOO_API_KEY"))
    if not url.startswith("https://"):
        raise SystemExit("Utilice HTTPS para proteger la API key.")
    common = xmlrpc.client.ServerProxy(url.rstrip("/") + "/xmlrpc/2/common", context=ssl.create_default_context())
    uid = common.authenticate(db, login, key, {})
    if not uid: raise SystemExit("Autenticación fallida.")
    rpc = xmlrpc.client.ServerProxy(url.rstrip("/") + "/xmlrpc/2/object", allow_none=True, context=ssl.create_default_context())
    def call(model, method, arguments, kwargs=None):
        values = {"context": {"allowed_company_ids": [args.company_id]}}
        values.update(kwargs or {})
        return rpc.execute_kw(db, uid, key, model, method, arguments, values)
    sources = call("dispatch.source", "search", [[("code", "=", args.source_code), ("company_id", "=", args.company_id)]])
    if len(sources) != 1: raise SystemExit("Configure una fuente única para esa compañía y código.")
    result = call("dispatch.source", "api_start_batch", [sources, args.batch_key, args.cutoff])
    snapshot_id = result["id"]
    if result["state"] in ("queued", "loading", "ready", "archived"):
        print(json.dumps(result)); return
    if result["state"] != "receiving": raise SystemExit("El lote requiere revisar el error en Odoo.")
    count = index = 0
    batch = []
    for row in rows(args.file):
        batch.append(row); count += 1
        if len(batch) == args.chunk_size:
            call("dispatch.snapshot", "api_append_chunk", [[snapshot_id], index, batch])
            index += 1; batch = []
    if batch:
        call("dispatch.snapshot", "api_append_chunk", [[snapshot_id], index, batch]); index += 1
    print(json.dumps(call("dispatch.snapshot", "api_finalize", [[snapshot_id], index, count])))


if __name__ == "__main__": main()
