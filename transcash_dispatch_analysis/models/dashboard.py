from collections import Counter
from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError
from ..services.engine import as_date, grouped, summarize, METRICS, GROUPS
from ..services.planning import build_transport_plan

READ_FIELDS = ["name", "source_id", "company_id", "external_number", "internal_number", "invoice_date", "customer", "city", "delivery", "warehouse", "seller",
    "state", "pending", "pending_lines", "pending_weight", "pending_boxes", "pending_pallets", "has_adjustment", "physically_completed", "source_warnings", "source_grain",
    "completion_date", "quality_flags", "quality_issue", "cutoff_date", "age_days", "lead_days", "lead_available", "sla_configured",
    "deadline", "sla_status", "late_days", "eligible", "mature", "on_time"]


class DispatchDashboard(models.AbstractModel):
    _name = "dispatch.dashboard"
    _description = "Servicio de tableros de despachos"

    @api.model
    def _access(self):
        if not self.env.su and not self.env.user.has_group("transcash_dispatch_analysis.group_dispatch_user"):
            raise AccessError(_("No tiene acceso a Análisis de despachos."))

    @api.model
    def _domain(self, filters=None):
        self._access()
        filters = filters or {}
        if not isinstance(filters, dict):
            raise ValidationError(_("Filtros inválidos."))
        domain = [("company_id", "in", self.env.companies.ids)]
        snapshot_id = filters.get("snapshot_id")
        if snapshot_id:
            snapshot = self.env["dispatch.snapshot"].browse(int(snapshot_id)).exists()
            snapshot.check_access_rights("read")
            snapshot.check_access_rule("read")
            if not snapshot or snapshot.state not in ("ready", "archived"):
                raise ValidationError(_("El corte todavía no está disponible."))
            domain += [("snapshot_id", "=", snapshot.id)]
        else:
            domain += [("snapshot_state", "=", "ready")]
        if filters.get("source_id"):
            domain += [("source_id", "=", int(filters["source_id"]))]
        for key, operator in (("date_from", ">="), ("date_to", "<=")):
            if filters.get(key):
                domain.append(("invoice_date", operator, as_date(filters[key]).isoformat()))
        if filters.get("date_from") and filters.get("date_to") and as_date(filters["date_from"]) > as_date(filters["date_to"]):
            raise ValidationError(_("La fecha inicial es posterior a la final."))
        for key in ("city", "delivery"):
            if filters.get(key):
                domain.append((key, "=", str(filters[key])[:300]))
        return domain

    @api.model
    def get_data(self, filters=None, board_id=False):
        filters = filters or {}
        domain = self._domain(filters)
        invoices = self.env["dispatch.invoice"]
        if invoices.search_count(domain) > 200_000:
            raise UserError(_("Seleccione una fuente o un período con menos de 200.000 facturas para el tablero. Las vistas dinámicas siguen disponibles."))
        rows = invoices.search_read(domain, READ_FIELDS)
        for row in rows:
            if not row.pop("lead_available"):
                row["lead_days"] = None
            for field in ("invoice_date", "completion_date", "cutoff_date", "deadline"):
                row[field] = str(row[field]) if row[field] else False
        stats = summarize(rows)
        scope = filters.get("planning_scope", "transcash")
        if scope not in ("transcash", "filtered"):
            raise ValidationError(_("Alcance de planificación no permitido."))
        pending_ids = [r["id"] for r in rows if r["pending"]]
        transport_lines = []
        for offset in range(0, len(pending_ids), 5000):
            transport_lines += self.env["dispatch.invoice.line"].search_read(
                [("invoice_id", "in", pending_ids[offset:offset + 5000]), ("pending_qty", ">", 0.000001)],
                ["invoice_id", "warehouse", "warehouse_code", "pending_qty", "pending_weight", "pending_pallets"])
        companies = self.env["res.company"].browse(sorted({r["company_id"][0] for r in rows}))
        packs = self.env["dispatch.transport.settings"]._planning_packs(companies)
        transport = build_transport_plan(rows, transport_lines, packs, scope)
        dates = sorted(r["invoice_date"] for r in rows if r["invoice_date"])
        period = {"date_from": filters.get("date_from") or (dates[0] if dates else False),
                  "date_to": filters.get("date_to") or (dates[-1] if dates else False), "basis": "invoice_date"}
        cities = grouped(rows, "city")
        cities.sort(key=lambda r: (-r["overdue"], -r["pending"], r["label"]))
        aging = [0] * 6
        for row in rows:
            if row["pending"]:
                age = row["age_days"]
                i = 0 if age <= 2 else 1 if age <= 5 else 2 if age <= 10 else 3 if age <= 30 else 4 if age <= 60 else 5
                aging[i] += 1
        pending = [r for r in rows if r["pending"]]
        pending.sort(key=lambda r: (0 if r["sla_status"] == "overdue" else 1 if r["sla_status"] == "due_today" else 2, -r["late_days"], -r["age_days"]))
        alerts = []
        if stats["same_day_warning"]:
            alerts.append({"kind": "warning", "title": "Todas las fechas medibles indican despacho el mismo día",
                "body": "Valide que UltimoDespacho corresponda a la salida física real. Los tiempos y el cumplimiento reflejan las fechas del origen y requieren esa validación."})
        if stats["overdue"]:
            alerts.append({"kind": "danger", "title": "%s facturas pendientes vencidas" % stats["overdue"], "body": "Priorice las facturas de la lista de atención y revise la capacidad de despacho por ciudad."})
        if stats["due_today"]:
            alerts.append({"kind": "warning", "title": "%s facturas vencen en la fecha de corte" % stats["due_today"], "body": "Todavía están dentro del plazo al cierre de ese día."})
        if stats["no_rule"]:
            alerts.append({"kind": "warning", "title": "%s facturas sin plazo configurado" % stats["no_rule"], "body": "Defina los días por ciudad y aplique los parámetros para medir su cumplimiento."})
        if stats["invalid"]:
            alerts.append({"kind": "info", "title": "%s facturas con datos por revisar" % stats["invalid"], "body": "Los datos no evaluables se muestran por separado del indicador de cumplimiento."})
        if stats["adjusted"]:
            alerts.append({"kind": "info", "title": "%s facturas con ajustes o devoluciones" % stats["adjusted"], "body": "Un saldo cerrado por devolución requiere revisión y no prueba un despacho físico completo."})
        if stats["source_warning_count"]:
            alerts.append({"kind": "info", "title": "%s facturas con errores de Excel en campos descriptivos" % stats["source_warning_count"], "body": "Se conservaron los errores y sus celdas de origen. No afectan cantidades ni fechas del indicador."})
        boards = self.env["dispatch.board"].search([])
        board = self.env["dispatch.board"].browse(int(board_id)).exists() if board_id else boards[:1]
        if board:
            board.check_access_rights("read")
            board.check_access_rule("read")
        widgets = []
        for widget in board.widget_ids if board else []:
            groups = grouped(rows, widget.dimension)
            if widget.chart_type == "line":
                selected = groups[-widget.top_n:]
            else:
                groups.sort(key=lambda r: (r[widget.metric] is not None, r[widget.metric] or 0), reverse=True)
                selected = groups[:widget.top_n]
            series = [{"label": r["label"], "value": None if widget.metric == "overdue" and not r["overdue_available"] else r[widget.metric]} for r in selected]
            if widget.chart_type == "donut" and len(groups) > len(selected):
                series.append({"label": "Otros", "value": sum(r[widget.metric] or 0 for r in groups[widget.top_n:])})
            widgets.append({"id": widget.id, "name": widget.name, "metric": widget.metric, "dimension": widget.dimension,
                            "chart_type": widget.chart_type, "series": series, "group_count": len(groups)})
        sources = self.env["dispatch.source"].search([])
        snapshots = self.env["dispatch.snapshot"].search([("state", "in", ["ready", "archived"])], limit=50)
        current = sources.mapped("active_snapshot_id")
        today = fields.Date.context_today(self)
        stale = [s for s in current if s.cutoff_date < today]
        if stale:
            alerts.insert(0, {"kind": "warning", "title": "Existen cortes anteriores a hoy", "body": "Los pendientes y atrasos se calculan a la fecha del corte, con el estado registrado entonces. Importe un corte nuevo para actualizar la operación."})
        return {"stats": stats, "cities": cities, "period": period, "transport": transport,
                "aging": [{"label": label, "value": value} for label, value in zip(["0–2 días", "3–5 días", "6–10 días", "11–30 días", "31–60 días", "Más de 60"], aging)],
                "priority": pending[:25], "alerts": alerts, "widgets": widgets,
                "boards": [{"id": b.id, "name": b.name} for b in boards], "board_id": board.id if board else False,
                "board_editable": bool(board and (board.owner_id == self.env.user or self.env.user.has_group("transcash_dispatch_analysis.group_dispatch_manager"))),
                "sources": [{"id": s.id, "name": s.name} for s in sources],
                "snapshots": [{"id": s.id, "name": s.name, "cutoff_date": str(s.cutoff_date)} for s in snapshots],
                "cutoffs": sorted({r["cutoff_date"] for r in rows}),
                "city_options": [r["city"] for r in invoices.read_group([("snapshot_state", "=", "ready")], ["city"], ["city"], lazy=False) if r["city"]],
                "delivery_options": [r["delivery"] for r in invoices.read_group([("snapshot_state", "=", "ready")], ["delivery"], ["delivery"], lazy=False) if r["delivery"]],
                "can_import": self.env.user.has_group("transcash_dispatch_analysis.group_dispatch_operator"),
                "can_configure": self.env.user.has_group("transcash_dispatch_analysis.group_dispatch_manager")}

    @api.model
    def get_detail_action(self, filters=None, category="all"):
        domain = self._domain(filters)
        additions = {"all": [], "pending": [("pending", "=", True)], "overdue": [("sla_status", "=", "overdue")],
                     "quality": [("quality_issue", "=", True)], "lead": [("lead_available", "=", True)],
                     "mature": [("mature", "=", True)], "no_rule": [("sla_configured", "=", False)]}
        if category not in additions:
            raise ValidationError(_("Categoría no permitida."))
        return {"type": "ir.actions.act_window", "name": _("Análisis de despachos"), "res_model": "dispatch.invoice",
                "view_mode": "list,form,pivot,graph", "domain": domain + additions[category]}

    @api.model
    def request_recalculation(self, filters=None):
        self._access()
        if not self.env.su and not self.env.user.has_group("transcash_dispatch_analysis.group_dispatch_manager"):
            raise AccessError(_("Solo un responsable puede reaplicar parámetros."))
        filters = filters or {}
        sources = self.env["dispatch.source"].search([("id", "=", int(filters["source_id"]))] if filters.get("source_id") else [])
        actions = []
        for snapshot in sources.mapped("active_snapshot_id"):
            actions.append(snapshot.action_recalculate())
        action = actions[0] if len(actions) == 1 else False
        if len(actions) > 1:
            action = {"type": "ir.actions.act_window", "name": _("Cortes con nuevos parámetros"),
                "res_model": "dispatch.snapshot", "view_mode": "list,form",
                "domain": [("id", "in", [a["params"]["snapshot_id"] for a in actions])]}
        return {"count": len(actions), "action": action}
