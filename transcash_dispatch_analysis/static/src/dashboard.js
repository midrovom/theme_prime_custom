/** @odoo-module **/
import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

const COLORS = ["#365eea", "#16a589", "#e6a23b", "#8759d4", "#e86b78", "#40a9c9", "#7d8da8", "#b29b72", "#3b7c6e", "#c17ab6", "#bbc4d8"];
const METRICS = [["total", "Facturas"], ["pending", "Pendientes"], ["overdue", "Vencidas"], ["mature_compliance", "Cumplimiento exigible (%)"], ["completed_compliance", "Despachadas a tiempo (%)"], ["lead_avg", "Tiempo promedio (días)"], ["lead_median", "Mediana de despacho (días)"], ["lead_p90", "P90 de despacho (días)"], ["pending_weight", "Peso pendiente (kg)"], ["pending_tons", "Toneladas pendientes"], ["invoiced_tons", "Toneladas facturadas conocidas"], ["dispatched_tons", "Toneladas despachadas"], ["invoiced_pallets", "Pallets facturados conocidos"], ["pending_pallets", "Pallets pendientes"]];
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
        this.state = useState({data: null, loading: true, error: "", builder: false, allLanes: false, appliedFilters: null, defaultsLoaded: false,
            savedFilters: [], selectedFavorite: "", favoriteName: "", audit: null, auditBusy: false,
            boardId: this.props.action?.params?.board_id || false,
            filters: {source_id: "", snapshot_id: "", date_from: "", date_to: "", city: "", delivery: "", planning_scope: "transcash", planning_grouping: "warehouse", warehouse_ids: []},
            draft: {name: "Nuevo indicador", metric: "pending", dimension: "city", chart_type: "bar", top_n: 10}});
        onWillStart(() => Promise.all([this.initialize(), this.loadSavedFilters()]));
    }
    async initialize() {
        try {
            this.state.filters = await this.orm.call("dispatch.dashboard", "get_default_filters", []);
            this.state.defaultsLoaded = true;
            await this.load();
        } catch (error) {
            this.state.loading = false;
            this.state.error = error.data?.message || error.message || "No fue posible cargar las fechas iniciales.";
        }
    }
    async retryLoad() {
        return this.state.defaultsLoaded ? this.load() : this.initialize();
    }
    async recentDates() {
        try {
            const defaults = await this.orm.call("dispatch.dashboard", "get_default_filters", []);
            Object.assign(this.state.filters, {date_from: defaults.date_from, date_to: defaults.date_to});
            await this.load();
        } catch (error) {
            this.notification.add(error.data?.message || error.message, {type: "danger"});
        }
    }
    async allDates() {
        Object.assign(this.state.filters, {date_from: "", date_to: ""});
        await this.load();
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
            {label: "Tiempo promedio", value: s.lead_avg === null ? "Sin medición" : `${this.format(s.lead_avg, 1)} días`, note: `${this.format(s.lead_count)} despachos medibles · días calendario`, category: "lead", tone: "blue"},
            {label: "P90 de despacho", value: s.lead_p90 === null ? "Sin medición" : `${this.format(s.lead_p90, 1)} días`, note: "90% de despachos medibles dentro de este tiempo", category: "lead", tone: "purple"},
        ];
    }
    amount(value, missing = 0, total = 0, suffix = "", digits = 2) {
        if (missing && total && missing >= total) return "Sin dato";
        return `${missing ? "Parcial · " : ""}${this.format(value, digits)}${suffix}`;
    }
    get cargoCards() {
        const s = this.state.data.stats;
        return [
            {label: "Toneladas facturadas", value: this.amount(s.invoiced_tons, s.invoiced_weight_missing_rows, s.line_count, " t"),
                note: s.invoiced_weight_missing_rows ? `${this.format(s.invoiced_weight_missing_rows)} registros sin peso facturado medible` : "Total facturado en las fechas seleccionadas", category: "all"},
            {label: "Toneladas despachadas", value: this.amount(s.dispatched_tons, s.dispatched_weight_missing_rows, s.line_count, " t"),
                note: "Peso de los despachos registrados al corte", category: "all"},
            {label: "Toneladas pendientes", value: `${this.format(s.pending_tons, 2)} t`, note: `${this.format(s.pending_weight, 2)} kg por despachar`, category: "pending"},
            {label: "Pallets facturados", value: this.amount(s.invoiced_pallets, s.invoiced_pallets_missing_rows, s.line_count),
                note: s.invoiced_pallets_missing_rows ? "El archivo debe informar PalletsFacturados" : "Pallets facturados informados en el archivo", category: "all"},
            {label: "Pallets pendientes", value: this.amount(s.pending_pallets, s.pending_pallets_missing_rows, s.pending_lines),
                note: s.pending_pallets_missing_rows ? "Hay registros sin pallets pendientes" : "Pallets equivalentes que faltan por despachar", category: "pending"},
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
        return `${!plan.complete && value !== null && value !== undefined ? "Parcial · " : ""}${this.planNumber(value, suffix)}`;
    }
    laneCalculation(lane) {
        const estimate = lane.estimate;
        if (!estimate) return "Faltan datos para calcular los vehículos.";
        const load = `${this.format(lane.pending_tons, 2)} t ÷ ${this.format(estimate.useful_tons, 2)} t por viaje → ${this.format(estimate.trips)} viaje(s).`;
        return `${load} Se necesitan ${this.planNumber(estimate.required_vehicles)} vehículo(s) para terminar en ${this.format(estimate.target_days)} días.`;
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
        // Dates belong to the current analysis, including open-ended ranges.
        // A saved view changes its other filters without replacing the period.
        const {date_from, date_to} = this.state.filters;
        this.state.filters = {...{source_id:"",snapshot_id:"",city:"",delivery:"",planning_scope:"transcash",planning_grouping:"warehouse",warehouse_ids:[]},
            ...JSON.parse(JSON.stringify(favorite.filters)), date_from, date_to};
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
            const filters = JSON.parse(JSON.stringify(this.state.filters));
            const data = await this.orm.call("dispatch.dashboard", "get_data", [filters, this.state.boardId]);
            if (request === this.requestNumber) {
                this.state.data = data;
                this.state.appliedFilters = filters;
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
        try {
            const action = await this.orm.call("dispatch.dashboard", "get_detail_action", [this.state.appliedFilters || this.state.filters, category]);
            return await this.action.doAction(action);
        } catch (error) {
            this.notification.add(error.data?.message || error.message || "No se pudo abrir el detalle.", {type: "danger"});
        }
    }
    async openAnalysis(warehouses = false) {
        try {
            const filters = this.state.appliedFilters || this.state.filters;
            const action = await this.orm.call("dispatch.dashboard", warehouses ? "get_warehouse_action" : "get_detail_action", warehouses ? [filters] : [filters, "all"]);
            if (!warehouses) action.views = [[false, "pivot"], [false, "graph"], [false, "list"], [false, "form"]];
            return await this.action.doAction(action);
        } catch (error) {
            this.notification.add(error.data?.message || error.message, {type: "danger"});
        }
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
        return this.format(value, widget.metric.endsWith("_tons") || widget.metric.endsWith("_pallets") ? 2 : widget.metric.includes("compliance") || widget.metric.startsWith("lead") ? 1 : 0) + (widget.metric.includes("compliance") ? "%" : widget.metric.endsWith("_tons") ? " t" : "");
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
    donutTotal(widget) {
        if (widget.series.length && widget.series.every(p => p.value === null)) return null;
        return widget.series.reduce((a, p) => a + (p.value || 0), 0);
    }
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
