from collections import Counter
from collections import defaultdict
from datetime import timedelta
import json
from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools.safe_eval import safe_eval
from ..services.engine import aggregate_invoice, as_date, evaluate, grouped, summarize, METRICS, GROUPS
from ..services.planning import build_transport_plan
from ..services.overview import pending_by_agreement, dispatch_progress, pending_plan_reconciliation
from ..services.timeliness import dispatch_timeliness

READ_FIELDS = ["name", "invoice_key", "snapshot_id", "source_id", "company_id", "external_number", "internal_number", "invoice_date", "customer", "city", "delivery", "warehouse", "seller",
    "state", "pending", "pending_lines", "pending_weight", "pending_boxes", "pending_pallets", "has_adjustment", "physically_completed", "source_warnings", "source_grain",
    "completion_date", "quality_flags", "quality_issue", "cutoff_date", "age_days", "lead_days", "lead_available", "sla_configured",
    "deadline", "sla_status", "late_days", "eligible", "mature", "on_time", "invoiced_weight", "dispatched_weight", "invoiced_weight_missing_rows", "dispatched_weight_missing_rows",
    "line_count", "invoiced_pallets", "invoiced_pallets_missing_rows", "pending_pallets_missing_rows", "sla_days", "sla_day_type"]


class DispatchDashboard(models.AbstractModel):
    _name = "dispatch.dashboard"
    _description = "Servicio de tableros de despachos"

    @api.model
    def _access(self):
        if not self.env.su and not self.env.user.has_group("transcash_dispatch_analysis.group_dispatch_user"):
            raise AccessError(_("No tiene acceso a Análisis de despachos."))

    @api.model
    def get_default_filters(self):
        self._access()
        today = fields.Date.context_today(self)
        return {"source_id": "", "snapshot_id": "", "city": "", "delivery": "", "warehouse_ids": [],
                "planning_scope": "transcash", "planning_grouping": "warehouse",
                "date_from": (today - timedelta(days=29)).isoformat(), "date_to": today.isoformat()}

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
            domain += [("is_current", "=", True)]
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
        warehouses = filters.get("warehouse_ids") or []
        if not isinstance(warehouses,list) or len(warehouses)>1000 or any(type(i) is not int or i<=0 for i in warehouses):
            raise ValidationError(_("Seleccione bodegas válidas."))
        if warehouses:
            domain.append(("warehouse_ids","in",warehouses))
        return domain

    @api.model
    def get_data(self, filters=None, board_id=False, include_ids=False):
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
        scope = filters.get("planning_scope", "transcash")
        if scope not in ("transcash", "filtered"):
            raise ValidationError(_("Alcance de planificación no permitido."))
        grouping = filters.get("planning_grouping", "warehouse")
        if grouping not in ("warehouse", "destination"):
            raise ValidationError(_("Forma de agrupar la carga no permitida."))
        warehouse_ids = filters.get("warehouse_ids") or []
        pending_ids = [r["id"] for r in rows if warehouse_ids or r["pending"]]
        transport_lines = []
        for offset in range(0, len(pending_ids), 5000):
            line_domain = [("invoice_id", "in", pending_ids[offset:offset + 5000])]
            line_domain += [("warehouse_id","in",warehouse_ids)] if warehouse_ids else [("pending_qty", ">", 0.000001)]
            line_fields = ["invoice_id", "warehouse", "warehouse_code", "pending_qty", "pending_weight", "pending_pallets", "pending_pallets_available"]
            if warehouse_ids: line_fields += ["raw_data"]
            transport_lines += self.env["dispatch.invoice.line"].search_read(line_domain,line_fields)
        if warehouse_ids:
            line_groups = defaultdict(list)
            for line in transport_lines:
                if line.get("raw_data"): line_groups[line["invoice_id"][0]].append(line["raw_data"])
            snapshots_for_scope = self.env["dispatch.snapshot"].browse(sorted({r["snapshot_id"][0] for r in rows}))
            packs_for_scope = {snapshot.id:snapshot.policy_pack or {} for snapshot in snapshots_for_scope}
            scoped = []
            for row in rows:
                if row["id"] not in line_groups: continue
                summary = aggregate_invoice(row["invoice_key"],line_groups[row["id"]],row["cutoff_date"])
                scoped.append({**row,**evaluate(summary,packs_for_scope.get(row["snapshot_id"][0],{}))})
            rows = scoped
        stats = summarize(rows)
        timeliness = dispatch_timeliness(rows, include_ids)
        timeliness_ids = timeliness.pop("detail_ids", {})
        agreements = pending_by_agreement(rows, include_ids, stats)
        progress = dispatch_progress(rows, transport_lines)
        companies = self.env["res.company"].browse(sorted({r["company_id"][0] for r in rows}))
        packs = self.env["dispatch.transport.settings"]._planning_packs(companies)
        transport = build_transport_plan(rows, transport_lines, packs, scope, grouping)
        transport["reconciliation"] = pending_plan_reconciliation(rows, transport, stats)
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
            def chart_value(group):
                if widget.metric == "overdue" and not group["overdue_available"]:
                    return None
                if widget.metric == "invoiced_pallets" and group["line_count"] and group["invoiced_pallets_missing_rows"] >= group["line_count"]:
                    return None
                if widget.metric == "pending_pallets" and group["pending_lines"] and group["pending_pallets_missing_rows"] >= group["pending_lines"]:
                    return None
                return group[widget.metric]
            series = [{"label": r["label"], "value": chart_value(r)} for r in selected]
            if widget.chart_type == "donut" and len(groups) > len(selected):
                other_values = [chart_value(r) for r in groups[widget.top_n:]]
                series.append({"label": "Otros", "value": sum(v for v in other_values if v is not None)
                    if any(v is not None for v in other_values) else None})
            widgets.append({"id": widget.id, "name": widget.name, "metric": widget.metric, "dimension": widget.dimension,
                            "chart_type": widget.chart_type, "series": series, "group_count": len(groups)})
        sources = self.env["dispatch.source"].search([])
        snapshots = self.env["dispatch.snapshot"].search([("state", "in", ["ready", "archived"])], limit=50)
        current = sources.mapped("active_snapshot_id")
        today = fields.Date.context_today(self)
        stale = [s for s in current if s.cutoff_date < today]
        if stale:
            alerts.insert(0, {"kind": "warning", "title": "Existen cortes anteriores a hoy", "body": "Los pendientes y atrasos se calculan a la fecha del corte, con el estado registrado entonces. Importe un corte nuevo para actualizar la operación."})
        detail_ids = False
        if include_ids:
            detail_ids={"all":[r["id"] for r in rows],"pending":[r["id"] for r in rows if r["pending"]],
                "overdue":[r["id"] for r in rows if r["sla_status"]=="overdue"],
                "quality":[r["id"] for r in rows if r["quality_issue"]],
                "lead":[r["id"] for r in rows if r["lead_days"] is not None],
                "mature":[r["id"] for r in rows if r["mature"]],
                "no_rule":[r["id"] for r in rows if not r["sla_configured"]],
                **timeliness_ids,
                "agreements": {group["key"]: group["invoice_ids"] for group in agreements["groups"]}}
            for group in agreements["groups"]:
                group.pop("invoice_ids")
        return {"stats": stats, "cities": cities, "period": period, "transport": transport,"detail_ids":detail_ids,
                "agreements": agreements, "dispatch_progress": progress, "timeliness": timeliness,
                "warehouse_options":self.env["dispatch.warehouse"].search_read([], ["name","code","company_id"],order="name,code"),
                "warehouse_scope":bool(warehouse_ids),
                "aging": [{"label": label, "value": value} for label, value in zip(["0–2 días", "3–5 días", "6–10 días", "11–30 días", "31–60 días", "Más de 60"], aging)],
                "priority": pending[:25], "alerts": alerts, "widgets": widgets,
                "boards": [{"id": b.id, "name": b.name} for b in boards], "board_id": board.id if board else False,
                "board_editable": bool(board and (board.owner_id == self.env.user or self.env.user.has_group("transcash_dispatch_analysis.group_dispatch_manager"))),
                "sources": [{"id": s.id, "name": s.name} for s in sources],
                "snapshots": [{"id": s.id, "name": s.name, "cutoff_date": str(s.cutoff_date)} for s in snapshots],
                "cutoffs": sorted({r["cutoff_date"] for r in rows}),
                "city_options": [r["city"] for r in invoices.read_group([("is_current", "=", True)], ["city"], ["city"], lazy=False) if r["city"]],
                "delivery_options": [r["delivery"] for r in invoices.read_group([("is_current", "=", True)], ["delivery"], ["delivery"], lazy=False) if r["delivery"]],
                "can_import": self.env.user.has_group("transcash_dispatch_analysis.group_dispatch_operator"),
                "can_configure": self.env.user.has_group("transcash_dispatch_analysis.group_dispatch_manager")}

    @api.model
    def validate_current_records(self):
        self._access()
        if not self.env.su and not self.env.user.has_group("transcash_dispatch_analysis.group_dispatch_manager"):
            raise AccessError(_("Solo un responsable puede validar y consolidar datos."))
        invoices = self.env["dispatch.invoice"].sudo()
        consolidated = invoices._initialize_unique_records(self.env.companies)
        company_domain=[("company_id","in",self.env.companies.ids)]
        current=invoices.search_count(company_domain+[("is_current","=",True)])
        historical=invoices.search_count(company_domain+[("snapshot_state","=","archived")])
        self.env.cr.execute("""SELECT count(*) FROM (SELECT company_id,invoice_type,internal_number
            FROM dispatch_invoice WHERE company_id=ANY(%s) AND is_current
            GROUP BY company_id,invoice_type,internal_number HAVING count(*)>1) duplicates""",(self.env.companies.ids,))
        return {"current":current,"historical_versions":historical,"current_duplicate_keys":self.env.cr.fetchone()[0],
                "consolidated_records":consolidated}

    @api.model
    def get_saved_filters(self):
        self._access()
        action=self.env.ref("transcash_dispatch_analysis.action_warehouse_analysis")
        filters=self.env["ir.filters"].search_read([("model_id","=","dispatch.invoice.line"),("action_id","=",action.id),
            "|",("user_id","=",False),("user_id","=",self.env.uid)], ["name","context"])
        result=[]
        for item in filters:
            try:context=safe_eval(item["context"] or "{}",{})
            except (ValueError,TypeError,NameError,SyntaxError):continue
            if isinstance(context,dict) and isinstance(context.get("dispatch_dashboard_filters"),dict):
                result.append({"id":item["id"],"name":item["name"],"filters":context["dispatch_dashboard_filters"],
                    "board_id":context.get("dispatch_board_id") or False})
        return result

    @api.model
    def save_dashboard_filter(self, name, filters=None, board_id=False):
        self._access()
        if not isinstance(name,str) or not name.strip() or len(name.strip())>120:
            raise ValidationError(_("Indique un nombre para el favorito (hasta 120 caracteres)."))
        filters=filters or {}
        domain=self._domain(filters)
        line_domain=[("invoice_id."+field,operator,value) for field,operator,value in domain if field!="warehouse_ids"]
        if filters.get("warehouse_ids"):line_domain.append(("warehouse_id","in",filters["warehouse_ids"]))
        if filters.get("planning_grouping", "warehouse") not in ("warehouse", "destination"):
            raise ValidationError(_("Forma de agrupar la carga no permitida."))
        allowed={key:filters[key] for key in ("source_id","snapshot_id","date_from","date_to","city","delivery","planning_scope","planning_grouping","warehouse_ids") if key in filters}
        if board_id:
            board=self.env["dispatch.board"].browse(int(board_id))
            board.check_access_rights("read");board.check_access_rule("read")
        action=self.env.ref("transcash_dispatch_analysis.action_warehouse_analysis")
        values={"name":name.strip(),"model_id":"dispatch.invoice.line","action_id":action.id,"user_id":self.env.uid,
            "domain":repr(line_domain),"context":repr({"dispatch_dashboard_filters":allowed,"dispatch_board_id":board_id or False})}
        model=self.env["ir.filters"]
        existing=model.search([("name","=",values["name"]),("user_id","=",self.env.uid),("model_id","=",values["model_id"]),("action_id","=",action.id)],limit=1)
        if existing:existing.write(values)
        else:existing=model.create(values)
        return {"id":existing.id,"name":existing.name}

    @api.model
    def get_detail_action(self, filters=None, category="all", agreement_key=False):
        domain = self._domain(filters)
        timeliness_categories = ("timely_completed", "late_completed", "overdue_pending")
        additions = {"all": [], "pending": [("pending", "=", True)], "overdue": [("sla_status", "=", "overdue")],
                     "quality": [("quality_issue", "=", True)], "lead": [("lead_available", "=", True)],
                     "mature": [("mature", "=", True)], "no_rule": [("sla_configured", "=", False)],
                     **{key: [] for key in timeliness_categories}}
        if category == "agreement":
            if not isinstance(agreement_key, str) or len(agreement_key) > 50:
                raise ValidationError(_("Plazo de entrega no permitido."))
            groups = self.get_data(filters, False, True)["detail_ids"]["agreements"]
            if agreement_key not in groups:
                raise ValidationError(_("El plazo no tiene pendientes con los filtros seleccionados."))
            additions[category] = [("id", "in", groups[agreement_key])]
        elif category not in additions:
            raise ValidationError(_("Categoría no permitida."))
        if category in timeliness_categories or (category != "agreement" and filters and filters.get("warehouse_ids")):
            ids=self.get_data(filters,False,True)["detail_ids"][category]
            additions[category]=[("id","in",ids)]
        return {"type": "ir.actions.act_window", "name": _("Análisis de despachos"), "res_model": "dispatch.invoice",
                "view_mode": "list,form,pivot,graph", "views": [(False, mode) for mode in ("list", "form", "pivot", "graph")],
                "domain": domain + additions[category], "target": "current"}

    @api.model
    def get_warehouse_action(self, filters=None):
        filters = filters or {}
        domain = self._domain(filters)
        line_domain = [("invoice_id." + field, operator, value) for field, operator, value in domain if field != "warehouse_ids"]
        if filters.get("warehouse_ids"):
            line_domain.append(("warehouse_id", "in", filters["warehouse_ids"]))
        action = self.env["ir.actions.actions"]._for_xml_id("transcash_dispatch_analysis.action_warehouse_analysis")
        return {**action, "domain": line_domain, "context": {}}

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
                "views": [(False, "list"), (False, "form")],
                "domain": [("id", "in", [a["params"]["snapshot_id"] for a in actions])]}
        return {"count": len(actions), "action": action}
