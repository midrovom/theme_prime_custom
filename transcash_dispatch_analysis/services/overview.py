"""Operational overview on the same unique, scoped invoices as the dashboard."""
import math

from .engine import EPS, as_date


def pending_by_agreement(rows, include_ids=False):
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
            "cities": set(), "deliveries": set(), "invoice_ids": []})
        group["pending"] += 1
        group["pending_tons"] += max(0, row.get("pending_weight") or 0) / 1000
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
    return {"groups": results, "due": due, "pending": sum(g["pending"] for g in results)}


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
