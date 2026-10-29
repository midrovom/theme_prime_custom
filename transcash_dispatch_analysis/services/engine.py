"""Business calculations shared by imports, dashboard and standalone tests.

Invoice quantities are evaluated LINE BY LINE; units from unrelated products
are never added into a dispatch percentage. A snapshot is not an event log.
"""
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from itertools import groupby
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import math
import sqlite3
import unicodedata

EPS = 0.000001
GROUPS = {"city", "delivery", "warehouse", "seller", "month"}
METRICS = {"total", "pending", "overdue", "mature_compliance", "completed_compliance", "lead_avg", "lead_median", "lead_p90", "pending_weight", "pending_tons", "invoiced_tons", "dispatched_tons"}


def normalize(value):
    text = "".join(c for c in unicodedata.normalize("NFKD", str(value or "")) if not unicodedata.combining(c))
    return " ".join(text.upper().split())


def number(value, field="cantidad"):
    if value in (None, ""):
        return 0.0
    if isinstance(value, bool):
        raise ValueError("Valor booleano inválido en %s." % field)
    try:
        result = float(str(value).replace(",", "."))
    except (TypeError, ValueError) as exc:
        raise ValueError("Valor no numérico en %s: %s" % (field, str(value)[:60])) from exc
    if not math.isfinite(result):
        raise ValueError("Valor no finito en %s." % field)
    return result


def as_date(value):
    if value in (False, None, ""):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, (float, int)) or str(value).replace(".", "", 1).isdigit():
        return (datetime(1899, 12, 30) + timedelta(days=float(value))).date()
    try:
        # API contract uses YYYY-MM-DD; timestamps must be normalized upstream.
        return date.fromisoformat(str(value))
    except ValueError as exc:
        raise ValueError("Fecha inválida: %s. Utilice YYYY-MM-DD." % value) from exc


def invoice_key(row):
    required = (normalize(row.get("TipoFactura")), str(row.get("NumeroFactura") or "").strip())
    if not all(required):
        raise ValueError("Cada línea debe incluir TipoFactura y NumeroFactura.")
    return json.dumps(list(required), ensure_ascii=False, separators=(",", ":"))


def unique_invoice_lines(rows):
    """Last observation per warehouse/product wins; distinct details survive."""
    unique, removed, changed = {}, 0, 0
    for row in rows:
        key = (normalize(row.get("CodBodega")), str(row.get("CodProducto") or "").strip())
        if key in unique:
            removed += 1
            changed += int(row != unique[key])
        unique[key] = row
    return list(unique.values()), removed, changed


def weight_metrics(row):
    """Known kg only; no unit-weight inference on mixed-product exports."""
    physical, pending, adjustment = (number(row.get(k)) for k in ("DespachoFisico", "Pendiente", "AjusteDevolucion"))
    reported = row.get("PesoDespacho")
    dispatched = number(reported, "PesoDespacho") if reported not in (None, "") else (0 if abs(physical) <= EPS else None)
    if dispatched is not None and dispatched < 0: dispatched = None
    pending_weight = number(row.get("PesoPendiente"), "PesoPendiente") if row.get("PesoPendiente") not in (None, "") else None
    pending_known = pending <= EPS or (pending_weight is not None and pending_weight > EPS)
    outstanding = max(0, pending_weight or 0) if pending > EPS else 0
    billed = row.get("PesoFacturado")
    if billed not in (None, ""):
        billed = number(billed, "PesoFacturado")
        if billed < 0: billed = None
    elif dispatched is not None and pending_known and pending >= -EPS:
        if abs(adjustment) <= EPS:
            billed = dispatched + outstanding
        elif row.get("PesoAjusteDevolucion") not in (None, ""):
            billed = dispatched + outstanding + number(row["PesoAjusteDevolucion"], "PesoAjusteDevolucion")
        else: billed = None
    else: billed = None
    return {"dispatched_weight": dispatched or 0, "dispatched_weight_available": dispatched is not None,
            "invoiced_weight": billed or 0, "invoiced_weight_available": billed is not None,
            "invoiced_weight_missing_rows": int(billed is None), "dispatched_weight_missing_rows": int(dispatched is None)}


def latest_invoice_versions(rows):
    """One published observation per company, type and invoice number."""
    latest = {}
    for row in rows:
        key = (row["company_id"],normalize(row["invoice_type"]),str(row["internal_number"]).strip())
        rank = (as_date(row["cutoff_date"]),row["snapshot_id"],row["id"])
        if key not in latest or rank > latest[key][0]: latest[key]=(rank,row["id"])
    return [value[1] for value in latest.values()]


def iter_invoice_groups(rows):
    """Use an on-disk spool to group unsorted large exports with bounded RAM."""
    with TemporaryDirectory(prefix="transcash_dispatch_") as directory:
        db = sqlite3.connect(str(Path(directory) / "rows.sqlite"))
        try:
            db.execute("CREATE TABLE source_rows (invoice_key TEXT, row_num INTEGER, payload TEXT)")
            buffer = []
            for i, row in enumerate(rows, 1):
                if not isinstance(row, dict):
                    raise ValueError("Cada registro debe ser un objeto con columnas del exportador.")
                if i > 500_000:
                    raise ValueError("El lote supera 500.000 líneas.")
                buffer.append((invoice_key(row), i, json.dumps(row, ensure_ascii=False, allow_nan=False)))
                if len(buffer) == 2000:
                    db.executemany("INSERT INTO source_rows VALUES (?,?,?)", buffer)
                    buffer.clear()
            if buffer:
                db.executemany("INSERT INTO source_rows VALUES (?,?,?)", buffer)
            db.commit()
            db.execute("CREATE INDEX row_key_idx ON source_rows(invoice_key,row_num)")
            cursor = db.execute("SELECT invoice_key,payload FROM source_rows ORDER BY invoice_key,row_num")
            for key, group in groupby(cursor, key=lambda item: item[0]):
                yield key, [json.loads(item[1]) for item in group]
        finally:
            db.close()


def aggregate_invoice(key, rows, cutoff):
    cutoff = as_date(cutoff)
    flags = set()
    dates = [as_date(r.get("FechaFactura")) for r in rows]
    dates_present = [d for d in dates if d]
    invoice_date = min(dates_present) if dates_present else None
    if not invoice_date or len(dates_present) != len(rows):
        flags.add("sin_fecha_factura")
    if len(set(dates_present)) > 1:
        flags.add("fechas_factura_inconsistentes")
    if invoice_date and invoice_date > cutoff:
        flags.add("factura_posterior_al_corte")
    cities = {normalize(r.get("Ciudad")) for r in rows}
    if not any(cities):
        flags.add("sin_ciudad")
    if len(cities) > 1:
        flags.add("ciudades_inconsistentes")
    deliveries = {str(r.get("Cond_Entrega") or "Sin condición").strip() for r in rows}
    if len(deliveries) > 1:
        flags.add("condiciones_inconsistentes")
    customer_keys = {str(r.get("CodCliente") or "") for r in rows}
    if len(customer_keys) > 1:
        flags.add("clientes_inconsistentes")
    keys = [(str(r.get("CodProducto") or ""), str(r.get("CodBodega") or "")) for r in rows]
    grains = {"product" if str(r.get("CodProducto") or "").strip() else "warehouse" for r in rows}
    source_grain = next(iter(grains)) if len(grains) == 1 else "mixed"
    if source_grain == "mixed":
        flags.add("granularidad_mixta")
    if len(keys) != len(set(keys)):
        flags.add("lineas_duplicadas")
    pending_lines = 0
    physical_any = False
    physical_full = True
    adjusted = False
    completion_dates = []
    last_dates = []
    pending_weight = boxes = pallets = 0.0
    weights = [weight_metrics(row) for row in rows]
    for r in rows:
        for required in ("Facturado", "DespachoFisico", "Pendiente"):
            if r.get(required) in (None, ""):
                raise ValueError("Falta %s en la factura %s / producto %s." % (required, first_number(rows), r.get("CodProducto", "")))
        q = number(r.get("Facturado"), "Facturado")
        physical = number(r.get("DespachoFisico"), "DespachoFisico")
        pending = number(r.get("Pendiente"), "Pendiente")
        adjustment = number(r.get("AjusteDevolucion"), "AjusteDevolucion")
        if abs(q - physical - adjustment - pending) > EPS:
            flags.add("cantidades_no_concilian")
        if r.get("Despachado") not in (None, "") and abs(number(r["Despachado"]) - physical - adjustment) > EPS:
            flags.add("despachado_no_concilia")
        pending_lines += int(pending > EPS)
        physical_any |= physical > EPS
        physical_full &= q > EPS and physical + EPS >= q
        adjusted |= abs(adjustment) > EPS
        if pending < -EPS:
            flags.add("saldo_negativo")
        if q < -EPS or physical < -EPS:
            flags.add("cantidad_negativa")
        last = as_date(r.get("UltimoDespacho"))
        if last:
            last_dates.append(last)
        if physical > EPS:
            if last:
                completion_dates.append(last)
                if invoice_date and last < invoice_date:
                    flags.add("despacho_anterior_a_factura")
                if last > cutoff:
                    flags.add("despacho_posterior_al_corte")
            else:
                flags.add("sin_fecha_despacho")
        # Do not net negative pending quantities against another product.
        if pending > EPS:
            pending_weight += max(0, number(r.get("PesoPendiente"), "PesoPendiente"))
            boxes += max(0, number(r.get("CajasPendientes"), "CajasPendientes"))
            pallets += max(0, number(r.get("PalletsPendientes"), "PalletsPendientes"))
    pending = pending_lines > 0
    physically_completed = bool(not pending and physical_full and not adjusted and completion_dates and "sin_fecha_despacho" not in flags)
    if pending:
        state = "partial" if physical_any else "pending"
    elif adjusted:
        state = "adjusted"
    elif "saldo_negativo" in flags:
        state = "excess"
    elif physically_completed:
        state = "done"
    else:
        state = "review"
    warehouses = sorted({str(r.get("Bodega") or r.get("CodBodega") or "Sin bodega") for r in rows})
    sellers = sorted({str(r.get("Vendedor") or "Sin vendedor") for r in rows})
    if len(sellers) > 1:
        flags.add("vendedores_inconsistentes")
    first = rows[0]
    return {
        "invoice_key": key,
        "name": "%s %s" % (first.get("TipoFactura", ""), first.get("NumeroFactura", "")),
        "external_number": str(first.get("Factura") or ""),
        "invoice_type": normalize(first.get("TipoFactura")),
        "internal_number": str(first.get("NumeroFactura") or "").strip(),
        "establishment": str(first.get("Establecimiento") or ""),
        "invoice_date": invoice_date.isoformat() if invoice_date else False,
        "invoice_time": str(first.get("HoraFactura") or ""),
        "customer_code": str(first.get("CodCliente") or ""),
        "customer": str(first.get("Cliente") or ""),
        "city": next(iter(cities)) if len(cities) == 1 and any(cities) else "SIN CIUDAD",
        "delivery": sorted(deliveries)[0],
        "warehouse": warehouses[0] if len(warehouses) == 1 else "VARIAS BODEGAS",
        "warehouses": " / ".join(warehouses),
        "seller": sellers[0] if len(sellers) == 1 else "VARIOS VENDEDORES",
        "state": state,
        "pending": pending,
        "pending_lines": pending_lines,
        "line_count": len(rows),
        "source_grain": source_grain,
        "pending_weight": pending_weight,
        "invoiced_weight": sum(w["invoiced_weight"] for w in weights),
        "dispatched_weight": sum(w["dispatched_weight"] for w in weights),
        "invoiced_weight_missing_rows": sum(w["invoiced_weight_missing_rows"] for w in weights),
        "dispatched_weight_missing_rows": sum(w["dispatched_weight_missing_rows"] for w in weights),
        "pending_boxes": boxes,
        "pending_pallets": pallets,
        "has_adjustment": bool(adjusted),
        "physically_completed": physically_completed,
        "completion_date": max(completion_dates).isoformat() if physically_completed else False,
        "last_dispatch_date": max(last_dates).isoformat() if last_dates else False,
        "quality_flags": sorted(flags),
        "quality_issue": bool(flags),
        "source_warnings": [dict(value, cell=cell) for r in rows for cell, value in (r.get("__excel_errors__") or {}).items()],
        "cutoff_date": cutoff.isoformat(),
    }


def first_number(rows):
    return str(rows[0].get("NumeroFactura") or "sin número")


def due_date(start, days, day_type="calendar", holidays=()):
    start = as_date(start)
    if days < 0 or int(days) != days:
        raise ValueError("El plazo debe ser un entero mayor o igual a cero.")
    days = int(days)
    if day_type == "calendar":
        return start + timedelta(days=days)
    if day_type != "business":
        raise ValueError("Tipo de días inválido.")
    holiday_set = {as_date(d) for d in holidays}
    result = start
    remaining = days
    while remaining:
        result += timedelta(days=1)
        if result.weekday() < 5 and result not in holiday_set:
            remaining -= 1
    return result


def elapsed_days(start, end, day_type="calendar", holidays=()):
    start, end = as_date(start), as_date(end)
    if end < start:
        return None
    if day_type == "calendar":
        return (end - start).days
    holiday_set = {as_date(d) for d in holidays}
    current, result = start, 0
    while current < end:
        current += timedelta(days=1)
        result += int(current.weekday() < 5 and current not in holiday_set)
    return result


def pick_policy(invoice, pack):
    matches = []
    inv_date = as_date(invoice.get("invoice_date"))
    for rule in pack.get("rules", []):
        if not rule.get("active", True):
            continue
        if rule.get("city_key") and rule["city_key"] != invoice["city"]:
            continue
        if rule.get("delivery_key") and rule["delivery_key"] != normalize(invoice["delivery"]):
            continue
        if rule.get("valid_from") and (not inv_date or inv_date < as_date(rule["valid_from"])):
            continue
        if rule.get("valid_to") and (not inv_date or inv_date > as_date(rule["valid_to"])):
            continue
        rank = 2 * bool(rule.get("city_key")) + bool(rule.get("delivery_key"))
        matches.append((rank, rule))
    if not matches:
        return None
    best = max(rank for rank, _ in matches)
    selected = [rule for rank, rule in matches if rank == best]
    if len(selected) != 1:
        raise ValueError("Hay plazos superpuestos para %s / %s." % (invoice["city"], invoice["delivery"]))
    return selected[0]


def evaluate(invoice, pack):
    result = dict(invoice)
    start = as_date(invoice.get("invoice_date"))
    end = as_date(invoice.get("completion_date"))
    cutoff = as_date(invoice["cutoff_date"])
    holidays = pack.get("holidays", [])
    rule = pick_policy(invoice, pack)
    result.update({
        "age_days": max(0, (cutoff - start).days) if start else 0,
        "lead_days": (end - start).days if start and end and end >= start and not invoice.get("quality_issue") else None,
        "sla_days": rule["max_days"] if rule else 0,
        "sla_day_type": rule.get("day_type", "calendar") if rule else "calendar",
        "sla_rule_id": rule.get("id") if rule else False,
        "sla_configured": bool(rule),
        "rule_snapshot": rule or {},
        "deadline": False,
        "sla_status": "no_rule",
        "late_days": 0,
        "sla_elapsed_days": None,
        "eligible": False,
        "mature": False,
        "on_time": False,
    })
    if start and rule:
        deadline = due_date(start, rule["max_days"], rule["day_type"], holidays)
        result["deadline"] = deadline.isoformat()
        check_date = end if end else cutoff
        result["sla_elapsed_days"] = elapsed_days(start, check_date, rule["day_type"], holidays)
        if check_date > deadline:
            result["late_days"] = elapsed_days(deadline, check_date, rule["day_type"], holidays)
    if invoice.get("quality_issue"):
        result["sla_status"] = "invalid"
    elif invoice.get("has_adjustment"):
        result["sla_status"] = "adjusted"
    elif not rule:
        pass
    elif not start or (not invoice["pending"] and not invoice["physically_completed"]):
        result["sla_status"] = "invalid"
    else:
        result["eligible"] = True
        deadline = as_date(result["deadline"])
        if invoice["physically_completed"]:
            result["mature"] = True
            result["on_time"] = end <= deadline
            result["sla_status"] = "on_time" if end <= deadline else "late"
        elif cutoff > deadline:
            result["mature"] = True
            result["sla_status"] = "overdue"
        else:
            result["sla_status"] = "due_today" if cutoff == deadline else "open"
    return result


def percentile(values, p):
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * p
    lo, hi = math.floor(position), math.ceil(position)
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (position - lo)


def summarize(rows):
    rows = list(rows)
    completed = [r for r in rows if r.get("physically_completed") and r.get("lead_days") is not None]
    assessed = [r for r in rows if r.get("eligible") and r.get("physically_completed")]
    mature = [r for r in rows if r.get("mature")]
    on_time = sum(bool(r.get("on_time")) for r in mature)
    lead = [r["lead_days"] for r in completed]
    pending_rows = [r for r in rows if r.get("pending")]
    pending_evaluable = sum(bool(r.get("eligible")) for r in pending_rows)
    return {
        "total": len(rows),
        "pending": sum(bool(r.get("pending")) for r in rows),
        "pending_unassessed": len(pending_rows) - pending_evaluable,
        "overdue_available": not pending_rows or bool(pending_evaluable),
        "partial": sum(r.get("state") == "partial" for r in rows),
        "overdue": sum(r.get("sla_status") == "overdue" for r in rows),
        "due_today": sum(r.get("sla_status") == "due_today" for r in rows),
        "completed": sum(bool(r.get("physically_completed")) for r in rows),
        "assessed_completed": len(assessed),
        "on_time": on_time,
        "mature_count": len(mature),
        "mature_compliance": 100 * on_time / len(mature) if mature else None,
        "completed_compliance": 100 * sum(bool(r.get("on_time")) for r in assessed) / len(assessed) if assessed else None,
        "lead_avg": sum(lead) / len(lead) if lead else None,
        "lead_median": percentile(lead, .5),
        "lead_p90": percentile(lead, .9),
        "lead_count": len(lead),
        "pending_weight": sum(r.get("pending_weight", 0) for r in rows if r.get("pending")),
        "pending_tons": sum(r.get("pending_weight", 0) for r in rows if r.get("pending")) / 1000,
        "invoiced_tons": sum(r.get("invoiced_weight", 0) for r in rows) / 1000,
        "dispatched_tons": sum(r.get("dispatched_weight", 0) for r in rows) / 1000,
        "invoiced_weight_missing_rows": sum(r.get("invoiced_weight_missing_rows", 0) for r in rows),
        "dispatched_weight_missing_rows": sum(r.get("dispatched_weight_missing_rows", 0) for r in rows),
        "pending_boxes": sum(r.get("pending_boxes", 0) for r in rows if r.get("pending")),
        "pending_pallets": sum(r.get("pending_pallets", 0) for r in rows if r.get("pending")),
        "no_rule": sum(not r.get("sla_configured") for r in rows),
        "invalid": sum(bool(r.get("quality_issue")) or r.get("sla_status") == "invalid" for r in rows),
        "adjusted": sum(bool(r.get("has_adjustment")) for r in rows),
        "source_warning_count": sum(bool(r.get("source_warnings")) for r in rows),
        "same_day_warning": len(lead) >= 30 and len({r.get("invoice_date") for r in completed}) >= 7 and all(value == 0 for value in lead),
    }


def grouped(rows, dimension):
    if dimension not in GROUPS:
        raise ValueError("Dimensión no permitida.")
    groups = defaultdict(list)
    for r in rows:
        label = str(r.get("invoice_date") or "")[:7] if dimension == "month" else r.get(dimension)
        groups[label or "Sin dato"].append(r)
    return [{"label": key, **summarize(value)} for key, value in sorted(groups.items())]


def metric_value(rows, metric):
    if metric not in METRICS:
        raise ValueError("Indicador no permitido.")
    values = summarize(rows)
    return None if metric == "overdue" and not values["overdue_available"] else values[metric]
