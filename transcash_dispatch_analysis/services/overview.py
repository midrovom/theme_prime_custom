"""Operational overview on the same unique, scoped invoices as the dashboard."""
import math
from decimal import Decimal, ROUND_HALF_UP

from .engine import EPS, as_date, normalize, summarize


def _display_rounding(total, parts):
    """Reconcile displayed hundredths explicitly; never alter group weights."""
    cent = Decimal("0.01")
    rounded = lambda value: Decimal(str(value or 0)).quantize(cent, rounding=ROUND_HALF_UP)
    delta = rounded(total) - sum((rounded(value) for value in parts), Decimal(0))
    return float(delta) if delta else 0.0


def pending_by_agreement(rows, include_ids=False, stats=None):
    if stats is None:
        rows = list(rows)
        stats = summarize(rows)
    groups = {}
    due = {key: 0 for key in ("overdue", "due_today", "next_3_days", "later", "review")}
    for row in rows:
        if not row.get("pending"):
            continue
        configured = bool(row.get("sla_configured"))
        days = int(row.get("sla_days") or 0) if configured else None
        day_type = row.get("sla_day_type") or "calendar"
        key = f"{day_type}:{days}" if configured else "no_rule"
        label = (f"{days} días " + ("hábiles" if day_type == "business" else "calendario")) if configured else "Sin plazo"
        group = groups.setdefault(key, {"key": key, "label": label, "days": days, "day_type": day_type,
            "configured": configured, "pending": 0, "pending_tons": 0.0, "within": 0, "overdue": 0, "review": 0,
            "pending_pallets": 0.0, "pending_pallets_missing_rows": 0, "pending_lines": 0,
            "cities": set(), "deliveries": set(), "invoice_ids": []})
        group["pending"] += 1
        group["pending_tons"] += max(0, row.get("pending_weight") or 0) / 1000
        group["pending_pallets"] += max(0, row.get("pending_pallets") or 0)
        group["pending_pallets_missing_rows"] += row.get("pending_pallets_missing_rows") or 0
        group["pending_lines"] += row.get("pending_lines") or 0
        group["cities"].add(row.get("city") or "Sin ciudad")
        group["deliveries"].add(row.get("delivery") or "Sin modalidad")
        if include_ids:
            group["invoice_ids"].append(row["id"])
        status = row.get("sla_status")
        if row.get("eligible") and status == "overdue":
            group["overdue"] += 1
            due["overdue"] += 1
        elif row.get("eligible") and status in ("open", "due_today"):
            group["within"] += 1
            deadline, cutoff = as_date(row.get("deadline")), as_date(row.get("cutoff_date"))
            remaining = (deadline - cutoff).days if deadline and cutoff else None
            due["due_today" if remaining == 0 else "next_3_days" if remaining is not None and 1 <= remaining <= 3 else "later"] += 1
        else:
            group["review"] += 1
            due["review"] += 1
    results = sorted(groups.values(), key=lambda g: (not g["configured"], g["days"] or 0, g["day_type"]))
    for group in results:
        group["cities"] = sorted(group["cities"])
        group["deliveries"] = sorted(group["deliveries"])
        if not include_ids:
            group.pop("invoice_ids")
    totals = {"pending": stats["pending"], "pending_tons": stats["pending_tons"], "pending_pallets": stats["pending_pallets"],
              "pending_pallets_missing_rows": stats["pending_pallets_missing_rows"], "pending_lines": stats["pending_lines"],
              **{key: sum(g[key] for g in results) for key in ("within", "overdue", "review")}}
    rounding = {"tons": _display_rounding(totals["pending_tons"], [g["pending_tons"] for g in results]),
                "pallets": _display_rounding(totals["pending_pallets"], [g["pending_pallets"] for g in results])}
    reconciled = (sum(g["pending"] for g in results) == totals["pending"]
        and math.isclose(sum(g["pending_tons"] for g in results), totals["pending_tons"], rel_tol=0, abs_tol=EPS)
        and math.isclose(sum(g["pending_pallets"] for g in results), totals["pending_pallets"], rel_tol=0, abs_tol=EPS))
    return {"groups": results, "due": due, "pending": sum(g["pending"] for g in results),
            "totals": totals, "rounding": rounding, "reconciled": reconciled}


def pending_plan_reconciliation(rows, transport, stats=None):
    """Separate delivery scope differences from missing/inconsistent line detail."""
    rows = list(rows)
    stats = stats if stats is not None else summarize(rows)
    excluded = [row for row in rows if row.get("pending") and transport["scope"] == "transcash"
                and normalize(row.get("delivery")) != "ENTREGA TRANSCASH"]
    outside_tons = sum(row.get("pending_weight") or 0 for row in excluded) / 1000
    planned_tons = transport["pending_tons"]
    unallocated = stats["pending_tons"] - outside_tons - planned_tons
    if abs(unallocated) <= EPS:
        unallocated = 0.0
    return {"total_tons": stats["pending_tons"], "planned_tons": planned_tons, "outside_plan_tons": outside_tons,
            "outside_plan_invoices": len(excluded), "unallocated_tons": unallocated,
            "detail_matches": unallocated == 0, "same_scope": not excluded,
            "rounding_tons": _display_rounding(stats["pending_tons"], [planned_tons, outside_tons, unallocated])}


def dispatch_progress(rows, pending_lines=()):
    """Use disjoint invoice states or a fully comparable weight cohort.

    Invoices with returns/adjustments or non-reconciling/unknown weights never
    turn into a fabricated delivered slice. Invoice count remains complete.
    """
    rows = list(rows)
    pending = sum(bool(row.get("pending")) for row in rows)
    unknown_pending_ids = set()
    for line in pending_lines:
        if (line.get("pending_qty") or 0) > EPS and (line.get("pending_weight") or 0) <= EPS:
            identity = line.get("invoice_id")
            unknown_pending_ids.add(identity[0] if isinstance(identity, (tuple, list)) else identity)
    billed_kg = dispatched_kg = pending_kg = 0.0
    measured = 0
    for row in rows:
        billed, physical = row.get("invoiced_weight"), row.get("dispatched_weight")
        outstanding = (row.get("pending_weight") or 0) if row.get("pending") else 0.0
        if (billed is None or physical is None or row.get("invoiced_weight_missing_rows") or row.get("dispatched_weight_missing_rows")
                or row.get("quality_issue") or row.get("has_adjustment") or row.get("id") in unknown_pending_ids):
            continue
        if not all(math.isfinite(value) and value >= 0 for value in (billed, physical, outstanding)) or billed <= EPS:
            continue
        if row.get("pending") and outstanding <= EPS:
            continue
        if not math.isclose(billed, physical + outstanding, rel_tol=0, abs_tol=0.01):
            continue
        measured += 1
        billed_kg += billed
        dispatched_kg += physical
        pending_kg += outstanding

    def chart(total, series, measured_count, excluded_count, unit, reported_total=None):
        return {"total": total, "reported_total": total if reported_total is None else reported_total,
            "series": [{"label": label, "value": value, "pct": 100 * value / total if total > EPS else None,
                        "color": color} for label, value, color in series],
            "measured_invoices": measured_count, "excluded_invoices": excluded_count,
            "partial": excluded_count > 0, "unit": unit, "available": total > EPS}

    return {
        "invoices": chart(len(rows), [("Sin pendiente", len(rows) - pending, "#16a589"), ("Con pendiente", pending, "#e6a23b")], len(rows), 0, "facturas"),
        "tons": chart((dispatched_kg + pending_kg) / 1000,
            [("Despachado", dispatched_kg / 1000, "#16a589"), ("Pendiente", pending_kg / 1000, "#e6a23b")],
            measured, len(rows) - measured, "t", billed_kg / 1000),
    }
