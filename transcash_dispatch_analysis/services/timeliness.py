"""Timeliness of unique, already scoped invoices; no import or stored writes.

The pie measures completed invoices, not individual truck trips or dispatch
events. Late completed invoices and outstanding overdue invoices are separate
cohorts. All delay magnitudes use calendar days AFTER the computed SLA deadline,
so business-day and calendar-day agreements can be compared without mixing units.
"""
from heapq import nsmallest

from .engine import as_date


def dispatch_timeliness(rows, include_ids=False):
    completed_total = pending_total = measured = timely = 0
    late = {"completed": [], "pending": []}
    identities = {key: [] for key in ("timely_completed", "late_completed", "overdue_pending")}
    for row in rows:
        completed = bool(row.get("physically_completed"))
        pending = bool(row.get("pending"))
        completed_total += int(completed)
        pending_total += int(pending)
        if (not row.get("eligible") or not row.get("sla_configured")
                or row.get("quality_issue") or row.get("has_adjustment")):
            continue
        cohort = "completed" if completed and not pending else "pending" if pending and not completed else None
        status = row.get("sla_status")
        if not cohort or (cohort == "completed" and status not in ("on_time", "late")):
            continue
        if cohort == "pending" and status != "overdue":
            continue
        try:
            start, deadline, cutoff = (as_date(row.get(field)) for field in ("invoice_date", "deadline", "cutoff_date"))
            end = as_date(row.get("completion_date")) if completed else cutoff
        except (ValueError, TypeError, OverflowError):
            continue
        if not all((start, deadline, cutoff, end)) or not start <= end <= cutoff or deadline < start:
            continue
        days = max(0, (end - deadline).days)
        if (status == "on_time" and days) or (status in ("late", "overdue") and not days):
            continue
        category = "timely_completed" if completed and not days else "late_completed" if completed else "overdue_pending"
        if include_ids:
            identities[category].append(row["id"])
        if completed:
            measured += 1
            timely += int(not days)
        if days:
            late[cohort].append((days, deadline, end, row))

    def delay_summary(items):
        ordered = nsmallest(10, items, key=lambda item: (-item[0], item[1], str(item[3].get("name") or ""), item[3]["id"]))
        return {"count": len(items), "avg_days": sum(item[0] for item in items) / len(items) if items else None,
            "max_days": max((item[0] for item in items), default=None), "available": bool(items),
            "top": [{"id": row["id"], "name": row.get("name") or str(row["id"]),
                "customer": row.get("customer") or "Sin cliente", "city": row.get("city") or "Sin ciudad",
                "deadline": deadline.isoformat(), "reference_date": end.isoformat(), "delay_days": days}
                for days, deadline, end, row in ordered]}

    series = [{"key": key, "label": label, "value": count, "pct": 100 * count / measured if measured else None, "color": color}
        for key, label, count, color in (("timely_completed", "A tiempo", timely, "#16a589"),
            ("late_completed", "Demorados", measured - timely, "#d35663"))]
    result = {"pie": {"available": bool(measured), "total": measured, "series": series,
            "completed_total": completed_total, "excluded_completed": completed_total - measured,
            "pending_total": pending_total},
        "delays": {key: delay_summary(items) for key, items in late.items()}, "day_unit": "calendar"}
    if include_ids:
        result["detail_ids"] = identities
    return result
