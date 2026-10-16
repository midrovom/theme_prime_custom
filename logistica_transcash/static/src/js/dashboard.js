/** @odoo-module **/
import { registry } from "@web/core/registry";
import { Component, onWillStart, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

class TranscashDashboard extends Component {
    static template = "logistica_transcash.OperacionDashboard";

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        const dateStr = (d) => [d.getFullYear(), String(d.getMonth() + 1).padStart(2, "0"), String(d.getDate()).padStart(2, "0")].join("-");
        const today = new Date();
        const start = new Date(today);
        start.setDate(start.getDate() - 89);
        this.state = useState({
            periodo: "semana", desde: dateStr(start), hasta: dateStr(today),
            loading: false, error: "", data: null,
            page: "resumen", busqueda: "", sort: "novedades",
        });
        onWillStart(() => this.refresh());
    }

    async refresh() {
        this.state.loading = true;
        this.state.error = "";
        try {
            this.state.data = await this.orm.call("transcash.dashboard.service", "get_dashboard", [
                this.state.periodo, this.state.desde, this.state.hasta,
            ]);
        } catch (err) {
            this.state.data = null;
            // No exponer trazas internas o nombres de tablas al usuario.
            // Los detalles técnicos quedan disponibles en el log de Odoo.
            console.error("Transcash dashboard: error consultando indicadores", err);
            this.state.error = this.readableError(err);
        } finally {
            this.state.loading = false;
        }
    }

    readableError(err) {
        const raw = String(err?.data?.message || err?.message || "");
        if (/AccessError|acceso|autorizaci[oó]n|permission|access denied/i.test(raw)) {
            return "Tu usuario no tiene permiso para consultar estos datos. Revisa el grupo de Analítica.";
        }
        if (/rango|fecha|date range/i.test(raw)) {
            return "Revisa el rango de fechas seleccionado (máximo 367 días).";
        }
        if (/network|conexi[oó]n|failed to fetch/i.test(raw)) {
            return "Se interrumpió la conexión. Verifica tu red y pulsa Reintentar.";
        }
        return "Odoo no pudo completar la consulta del dashboard. Pulsa Reintentar; si continúa, revisa el log del servicio Odoo en el servidor.";
    }
    qualityPct(value) {
        const v = Number(value) || 0;
        return Math.min(100, Math.max(0, v));
    }
    topRows(section, field, limit = 6) {
        const rows = (this.state.data && this.state.data[section]) || [];
        return [...rows].sort((a, b) => (Number(b[field]) || 0) - (Number(a[field]) || 0)).slice(0, limit);
    }
    barWidth(section, field, value) {
        const rows = (this.state.data && this.state.data[section]) || [];
        const max = rows.reduce((v, r) => Math.max(v, Number(r[field]) || 0), 0);
        return max ? Math.min(100, Math.max(0, 100 * (Number(value) || 0) / max)).toFixed(1) : 0;
    }

    changePeriod(ev) { this.state.periodo = ev.target.value; this.refresh(); }
    changeStart(ev) { this.state.desde = ev.target.value; this.refresh(); }
    changeEnd(ev) { this.state.hasta = ev.target.value; this.refresh(); }
    changeSearch(ev) { this.state.busqueda = ev.target.value; }
    changeSort(ev) { this.state.sort = ev.target.value; }
    showSection(ev) {
        const page = ev.currentTarget.dataset.page;
        this.state.page = page;
        this.state.busqueda = "";
        this.state.sort = ["marcas", "proveedores_producto"].includes(page) ? "reportes" : (page === "destinos" ? "viajes" : "novedades");
    }
    openIncidents() { this.action.doAction("logistica_transcash.action_transcash_novedades"); }
    number(v) { return new Intl.NumberFormat("es-EC", { maximumFractionDigits: 2 }).format(v || 0); }
    percent(v) { return this.number(v) + "%"; }
    pageTitle() { return ({resumen: "Panorama logístico", transportistas: "Empresas de transporte", choferes: "Desempeño por chofer", destinos: "Viajes y destinos", marcas: "Roturas por marca", proveedores_producto: "Proveedores de productos"})[this.state.page] || "Transcash"; }
    isProductPage() { return ["marcas", "proveedores_producto"].includes(this.state.page); }
    tableRows() {
        const list = (this.state.data && this.state.data[this.state.page]) || [];
        const term = this.state.busqueda.trim().toLocaleLowerCase();
        const filtered = !term ? list : list.filter((r) => (r.nombre || "").toLocaleLowerCase().includes(term));
        const k = this.state.sort;
        return [...filtered].sort((a, b) => (Number(b[k] || 0) - Number(a[k] || 0)) || (a.nombre || "").localeCompare(b.nombre || ""));
    }
    currentDataset() { return this.state.page === "resumen" ? "all" : this.state.page; }
    exportCurrent() { this.download(this.currentDataset()); }
    exportEverything() { this.download("all"); }
    download(dataset) {
        // This endpoint revalidates the role, date range and company scope on the server.
        const params = new URLSearchParams({dataset, periodo: this.state.periodo,
            desde: this.state.desde, hasta: this.state.hasta,
            q: dataset === "all" ? "" : this.state.busqueda,
            sort: dataset === "all" ? "" : this.state.sort});
        window.location.assign("/transcash/dashboard/export/xlsx?" + params.toString());
    }
}
registry.category("actions").add("transcash_dashboard", TranscashDashboard);
