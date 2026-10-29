/** @odoo-module **/
import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

const COLORS = ["#365eea", "#16a589", "#e6a23b", "#8759d4", "#e86b78", "#40a9c9", "#7d8da8", "#b29b72", "#3b7c6e", "#c17ab6", "#bbc4d8"];
const METRICS = [["total", "Facturas"], ["pending", "Pendientes"], ["overdue", "Vencidas"], ["mature_compliance", "Cumplimiento exigible (%)"], ["completed_compliance", "Despachadas a tiempo (%)"], ["lead_avg", "Tiempo promedio (días)"], ["lead_median", "Mediana de despacho (días)"], ["lead_p90", "P90 de despacho (días)"], ["pending_weight", "Peso pendiente (kg)"], ["pending_tons", "Toneladas pendientes"], ["invoiced_tons", "Toneladas facturadas conocidas"], ["dispatched_tons", "Toneladas despachadas"]];
const DIMENSIONS = [["city", "Ciudad"], ["delivery", "Modalidad"], ["warehouse", "Bodega"], ["seller", "Vendedor"], ["month", "Mes de factura"]];

export class DispatchDashboard extends Component {
    static template = "transcash_dispatch_analysis.Dashboard";
    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.requestNumber = 0;
        this.metrics = METRICS;
        this.dimensions = DIMENSIONS;
        this.state = useState({data: null, loading: true, error: "", builder: false, allLanes: false,
            savedFilters: [], selectedFavorite: "", favoriteName: "", audit: null, auditBusy: false,
            boardId: this.props.action?.params?.board_id || false,
            filters: {source_id: "", snapshot_id: "", date_from: "", date_to: "", city: "", delivery: "", planning_scope: "transcash", warehouse_ids: []},
            draft: {name: "Nuevo indicador", metric: "pending", dimension: "city", chart_type: "bar", top_n: 10}});
        onWillStart(() => Promise.all([this.load(), this.loadSavedFilters()]));
    }
    format(value, digits = 0) {
        return value === null || value === undefined ? "Sin medición" : new Intl.NumberFormat("es-EC", {maximumFractionDigits: digits, minimumFractionDigits: digits}).format(value);
    }
    date(value) {
        if (!value) return "Sin fecha";
        return value.split("-").reverse().join("/");
    }
    get kpis() {
        const s = this.state.data.stats;
        return [
            {label: "Facturas analizadas", value: this.format(s.total), note: "Una vez por factura", category: "all", tone: "blue"},
            {label: "Pendientes de despacho", value: this.format(s.pending), note: `${this.format(s.partial)} con despacho parcial`, category: "pending", tone: "amber"},
            {label: "Pendientes vencidas", value: s.overdue_available ? this.format(s.overdue) : "Sin medición", note: `${this.format(s.pending_unassessed)} pendientes sin evaluar · ${this.format(s.due_today)} vencen al corte`, category: "overdue", tone: "red"},
            {label: "Cumplimiento del período", value: s.mature_compliance === null ? "Sin medición" : `${this.format(s.mature_compliance, 1)}%`, note: `${this.format(s.on_time)} a tiempo / ${this.format(s.mature_count)} exigibles`, category: "mature", tone: "green"},
            {label: "Toneladas pendientes", value: `${this.format(s.pending_tons, 2)} t`, note: `${this.format(s.pending_weight, 2)} kg · 1 t = 1.000 kg`, category: "pending", tone: "amber"},
            {label: "Toneladas facturadas conocidas", value: `${s.invoiced_weight_missing_rows ? 'Parcial · ' : ''}${this.format(s.invoiced_tons, 2)} t`, note: s.invoiced_weight_missing_rows ? `${this.format(s.invoiced_weight_missing_rows)} registros requieren PesoFacturado o peso del ajuste` : "Peso facturado medible del período", category: "all", tone: "blue"},
            {label: "Toneladas despachadas", value: `${this.format(s.dispatched_tons, 2)} t`, note: s.dispatched_weight_missing_rows ? `Parcial: ${this.format(s.dispatched_weight_missing_rows)} registros sin peso de despacho` : "PesoDespacho informado por el origen", category: "all", tone: "green"},
            {label: "Tiempo promedio", value: s.lead_avg === null ? "Sin medición" : `${this.format(s.lead_avg, 1)} días`, note: `${this.format(s.lead_count)} despachos medibles · días calendario`, category: "lead", tone: "blue"},
            {label: "P90 de despacho", value: s.lead_p90 === null ? "Sin medición" : `${this.format(s.lead_p90, 1)} días`, note: "90% de despachos medibles dentro de este tiempo", category: "lead", tone: "purple"},
        ];
    }
    get periodLabel() {
        const period = this.state.data.period;
        return period.date_from && period.date_to ? `${this.date(period.date_from)} al ${this.date(period.date_to)}` : "Sin fechas disponibles";
    }
    get transportLanes() {
        const lanes = this.state.data.transport.lanes;
        return this.state.allLanes ? lanes : lanes.slice(0, 10);
    }
    planNumber(value, suffix = "") {
        return value === null || value === undefined ? "Sin estimación" : `${this.format(value)}${suffix}`;
    }
    planTotal(key, suffix = "") {
        const plan = this.state.data.transport;
        const value = plan[key] ?? plan[`known_${key}`];
        return this.planNumber(value, suffix);
    }
    toggleWarehouse(id, checked) {
        const ids = this.state.filters.warehouse_ids || [];
        this.state.filters.warehouse_ids = checked ? [...new Set([...ids, id])] : ids.filter(value => value !== id);
    }
    async loadSavedFilters() {
        try {
            this.state.savedFilters = await this.orm.call("dispatch.dashboard", "get_saved_filters", []);
        } catch (error) {
            this.notification.add(error.data?.message || error.message, {type: "warning"});
        }
    }
    async saveFavorite() {
        try {
            if (!this.state.favoriteName.trim()) {
                this.notification.add("Escribe un nombre para guardar la vista.", {type: "warning"});
                return;
            }
            await this.load();
            if (!this.state.data) return;
            const saved = await this.orm.call("dispatch.dashboard", "save_dashboard_filter", [this.state.favoriteName, this.state.filters, this.state.boardId]);
            await this.loadSavedFilters();
            this.state.selectedFavorite = String(saved.id);
            this.notification.add("Vista guardada en Favoritos de Odoo.", {type: "success"});
        } catch (error) {
            this.notification.add(error.data?.message || error.message, {type: "danger"});
        }
    }
    async loadFavorite() {
        const favorite = this.state.savedFilters.find(f => f.id === Number(this.state.selectedFavorite));
        if (!favorite) return;
        this.state.filters = {...{source_id:"",snapshot_id:"",date_from:"",date_to:"",city:"",delivery:"",planning_scope:"transcash",warehouse_ids:[]}, ...JSON.parse(JSON.stringify(favorite.filters))};
        this.state.boardId = favorite.board_id || false;
        this.state.favoriteName = favorite.name;
        await this.load();
    }
    async validateRecords() {
        this.state.auditBusy = true;
        try {
            this.state.audit = await this.orm.call("dispatch.dashboard", "validate_current_records", []);
            await this.load();
        } catch (error) {
            this.notification.add(error.data?.message || error.message, {type: "danger"});
        } finally { this.state.auditBusy = false; }
    }
    async load() {
        const request = ++this.requestNumber;
        this.state.loading = true;
        this.state.error = "";
        try {
            const data = await this.orm.call("dispatch.dashboard", "get_data", [this.state.filters, this.state.boardId]);
            if (request === this.requestNumber) {
                this.state.data = data;
                this.state.boardId = data.board_id;
            }
        } catch (error) {
            if (request === this.requestNumber) {
                this.state.error = error.data?.message || error.message || "No fue posible cargar el tablero.";
                this.state.data = null;
            }
        } finally {
            if (request === this.requestNumber) this.state.loading = false;
        }
    }
    async detail(category) {
        const action = await this.orm.call("dispatch.dashboard", "get_detail_action", [this.state.filters, category]);
        return this.action.doAction(action);
    }
    openInvoice(id) {
        return this.action.doAction({type: "ir.actions.act_window", res_model: "dispatch.invoice", res_id: id, views: [[false, "form"]], target: "current"});
    }
    openAction(name) {
        return this.action.doAction(`transcash_dispatch_analysis.${name}`);
    }
    async recalculate() {
        try {
            const result = await this.orm.call("dispatch.dashboard", "request_recalculation", [this.state.filters]);
            if (result.action) {
                return this.action.doAction(result.action);
            }
            this.notification.add("No hay un corte vigente al que aplicar los parámetros.", {type: "info"});
        } catch (error) {
            this.notification.add(error.data?.message || error.message, {type: "danger"});
        }
    }
    async newBoard() {
        const ids = await this.orm.create("dispatch.board", [{name: "Mi tablero de despachos"}]);
        this.state.boardId = ids[0];
        await this.load();
        this.state.builder = true;
    }
    editBoard() {
        return this.action.doAction({type: "ir.actions.act_window", res_model: "dispatch.board", res_id: this.state.boardId, views: [[false, "form"]], target: "new"}, {onClose: () => this.load()});
    }
    async saveWidget() {
        try {
            if (!this.state.boardId) await this.newBoard();
            const d = this.state.draft;
            await this.orm.create("dispatch.widget", [{...d, top_n: Number(d.top_n), board_id: this.state.boardId}]);
            this.state.builder = false;
            await this.load();
        } catch (error) {
            this.notification.add(error.data?.message || error.message, {type: "danger"});
        }
    }
    barWidth(widget, value) {
        const max = widget.metric.includes("compliance") ? 100 : Math.max(1, ...widget.series.map(p => p.value || 0));
        return Math.max(0, Math.min(100, 100 * (value || 0) / max));
    }
    metricFormat(widget, value) {
        if (value === null) return "Sin medición";
        return this.format(value, widget.metric.endsWith("_tons") ? 2 : widget.metric.includes("compliance") || widget.metric.startsWith("lead") ? 1 : 0) + (widget.metric.includes("compliance") ? "%" : widget.metric.endsWith("_tons") ? " t" : "");
    }
    color(index) { return COLORS[index % COLORS.length]; }
    donutStyle(widget) {
        const total = widget.series.reduce((a, p) => a + Math.max(0, p.value || 0), 0);
        if (!total) return "background:#e8edf5";
        let position = 0;
        const stops = widget.series.map((p, i) => {
            const from = position;
            position += 100 * Math.max(0, p.value || 0) / total;
            return `${this.color(i)} ${from}% ${position}%`;
        });
        return `background:conic-gradient(${stops.join(",")})`;
    }
    donutTotal(widget) { return widget.series.reduce((a, p) => a + (p.value || 0), 0); }
    linePoints(widget) {
        const max = widget.metric.includes("compliance") ? 100 : Math.max(1, ...widget.series.map(p => p.value || 0));
        return widget.series.map((p, i) => ({...p, x: 20 + i * 560 / Math.max(1, widget.series.length - 1), y: 165 - 140 * (p.value || 0) / max}));
    }
    lineSegments(widget) {
        const result = [];
        let points = [];
        for (const point of this.linePoints(widget)) {
            if (point.value === null) {
                if (points.length) result.push(points.join(" "));
                points = [];
            } else points.push(`${point.x},${point.y}`);
        }
        if (points.length) result.push(points.join(" "));
        return result;
    }
}
registry.category("actions").add("transcash_dispatch_dashboard", DispatchDashboard);
