/** @odoo-module **/
import { registry } from "@web/core/registry";
import { Component, onWillStart, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

class TranscashDashboard extends Component {
    static template = "logistica_transcash.OperacionDashboard";

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        const iso = (date) => [date.getFullYear(), String(date.getMonth()+1).padStart(2, "0"), String(date.getDate()).padStart(2, "0")].join("-");
        const now = new Date();
        const start = new Date(now); start.setDate(start.getDate() - 89);
        this.state = useState({desde: iso(start), hasta: iso(now), periodo: "semana", base: "registro",
            loading: false, error: "", data: null, page: "resumen", busqueda: "", sort: "", audit: [], auditError: ""});
        onWillStart(() => this.refresh());
    }

    async refresh() {
        this.state.loading = true;
        this.state.error = "";
        try {
            const data = await this.orm.call("transcash.dashboard.service", "get_dashboard",
                [this.state.periodo, this.state.desde, this.state.hasta, this.state.base]);
            this.state.data = data;
            if (!this.allowedSections().some((n) => n.id === this.state.page)) this.state.page = "resumen";
        } catch (error) {
            this.state.data = null;
            console.error("Error cargando los indicadores de Logística Transcash:", error);
            this.state.error = error?.data?.message || error?.message || "No fue posible consultar los indicadores. Revise el log de Odoo.";
        } finally { this.state.loading = false; }
    }

    allowedSections() {
        const perms = this.state.data?.permisos || {};
        const sections = [
            {id:"resumen",label:"Resumen ejecutivo",icon:"◈"},
            {id:"guias",label:"Guías y estados",icon:"▤"},
            {id:"rutas",label:"Hojas de ruta",icon:"⌁"},
            {id:"embarques",label:"Embarques y viajes",icon:"▣"},
            {id:"destinos",label:"Destinos",icon:"⌾"},
            {id:"transportistas",label:"Transportistas",icon:"⛟"},
            {id:"choferes",label:"Choferes",icon:"♧"},
            {id:"incidencias",label:"Novedades / roturas",icon:"!"},
        ];
        if (perms.finanzas) sections.push({id:"liquidaciones",label:"Liquidaciones",icon:"$"});
        if (perms.comercial) sections.push({id:"marcas",label:"Marcas · privado",icon:"▤"}, {id:"proveedores_producto",label:"Prov. producto · privado",icon:"▦"});
        if (perms.auditoria_menus) sections.push({id:"auditoria",label:"Diagnóstico de menús",icon:"⚙"});
        return sections;
    }

    showSection(ev) {
        const page = ev.currentTarget.dataset.page;
        if (!this.allowedSections().some(n => n.id === page)) return;
        this.state.page = page; this.state.busqueda = ""; this.state.sort = "";
        if (page === "auditoria" && !this.state.audit.length) this.auditMenus();
    }
    changeBase(ev) { this.state.base = ev.target.value; this.refresh(); }
    changePeriod(ev) { this.state.periodo = ev.target.value; this.refresh(); }
    changeStart(ev) { this.state.desde = ev.target.value; this.refresh(); }
    changeEnd(ev) { this.state.hasta = ev.target.value; this.refresh(); }
    changeSearch(ev) { this.state.busqueda = ev.target.value; }
    changeSort(ev) { this.state.sort = ev.target.value; }
    async auditMenus() {
        this.state.auditError = "";
        try { this.state.audit = await this.orm.call("transcash.dashboard.service", "audit_menus", []); }
        catch (e) { this.state.auditError = e?.data?.message || e?.message || "No fue posible auditar los menús."; }
    }
    async openMenu(ev) {
        const id = Number(ev.currentTarget.dataset.action);
        if (id) await this.action.doAction(id);
    }
    async openRecord(ev) {
        const model = ev.currentTarget.dataset.model;
        const id = Number(ev.currentTarget.dataset.id);
        if (!model || !id) return;
        await this.action.doAction({type:"ir.actions.act_window",res_model:model,res_id:id,
            views:[[false,"form"]],target:"current"});
    }
    number(value) { return new Intl.NumberFormat("es-EC", { maximumFractionDigits: 3 }).format(Number(value) || 0); }
    currency(value) { return (this.state.data?.divisa || "") + " " + new Intl.NumberFormat("es-EC", {minimumFractionDigits:2,maximumFractionDigits:2}).format(Number(value)||0); }
    formatValue(v, kind) {
        if (kind === "number") return this.number(v);
        if (kind === "currency") return this.number(v);
        if (kind === "percentage") return this.number(v) + "%";
        return v === null || v === undefined || v === false ? "—" : String(v);
    }
    kpiCards() {
        const k = this.state.data?.kpis || {};
        const out = [
            {label:"Guías registradas",value:k.guias,detail:"Operación en el periodo"},
            {label:"Sin hoja de ruta",value:k.guias_sin_ruta,detail:"Registradas y disponibles"},
            {label:"Hojas de ruta",value:k.rutas,detail:"Incluye borradores"},
            {label:"Embarques programados",value:k.viajes,detail:"Incluye preparación"},
            {label:"Salidas reales",value:k.salidas_reales,detail:"Con fecha real de salida"},
            {label:"Entregas de chofer",value:k.guias_entregadas,detail:"Guías cerradas o posteriores"},
            {label:"Peso (kg)",value:k.kg,detail:"Toneladas: " + this.number(k.toneladas)},
            {label:"Superficie (m²)",value:k.m2,detail:"Sin mezclar con unidades"},
            {label:"Metros lineales",value:k.metros_lineales,detail:"No se mezclan con m²"},
            {label:"Unidades",value:k.unidades,detail:"Productos contados en unidades"},
            {label:"Pallets / cajas",value:this.number(k.pallets)+" / "+this.number(k.cajas),detail:"Conversión informativa",text:true},
            {label:"Con novedades",value:k.guias_novedad,detail:"Abiertas: " + this.number(k.novedades_abiertas)},
            {label:"Con roturas",value:k.guias_rotura,detail:"Reportes: " + this.number(k.reportes_rotura)},
        ];
        if (this.state.data?.permisos?.finanzas) {
            out.push({label:"Liquidaciones",value:k.liquidaciones,detail:"Pendientes: " + this.number(k.liquidaciones_pendientes)});
            if (!this.state.data.permisos.monedas_multiples)
                out.push({label:"Saldo a pagar",value:k.saldo_pendiente,detail:"Pagado: " + this.currency(k.total_pagado),money:true});
            else out.push({label:"Saldos por divisa",value:"Ver liquidaciones",detail:"No se suman monedas distintas",text:true});
        }
        return out;
    }
    pageTitle() {
        return ({resumen:"Centro de control logístico",guias:"Guías y estados",rutas:"Hojas de ruta",
            embarques:"Embarques y viajes",destinos:"Movimiento por destino",transportistas:"Análisis por transportista",
            choferes:"Análisis por chofer",incidencias:"Novedades y roturas",liquidaciones:"Liquidaciones y pagos",
            marcas:"Roturas y exposición por marca",proveedores_producto:"Proveedores de productos",auditoria:"Revisión de menús y acciones"})[this.state.page] || "Logística";
    }
    columns() {
        const n = (key,label,type="text") => ({key,label,type});
        const load = [n("kg","Kg","number"),n("m2","m²","number"),n("metros_lineales","m lin.","number"),n("unidades","Unid.","number")];
        switch (this.state.page) {
            case "guias":return [n("nombre","Guía"),n("estado","Estado"),n("documento","Documento"),n("destino","Destino"),n("transportista","Transporte"),n("ruta","Ruta"), ...load];
            case "rutas":return [n("nombre","Ruta"),n("estado","Estado"),n("destino","Destino"),n("transportista","Transporte"),n("guias","Guías","number"), ...load];
            case "embarques":return [n("nombre","Viaje"),n("estado","Estado"),n("transportista","Transporte"),n("guias","Guías","number"),n("rutas","Rutas","number"),...load];
            case "destinos":case "transportistas":case "choferes":return [n("nombre","Nombre"),n("guias","Guías","number"),n("viajes","Viajes","number"),...load,n("novedades","Novedades","number"),n("roturas","Roturas","number")];
            case "incidencias":return [n("nombre","Guía"),n("destino","Destino"),n("estado","Incidencia"),n("reportes","Reportes","number"),n("fecha","Fecha")];
            case "liquidaciones":return [n("nombre","Liquidación"),n("estado","Estado"),n("transportista","Transporte"),n("moneda","Moneda"),n("total","Acordado","currency"),n("pagado","Pagado","currency"),n("pendiente","Saldo","currency")];
            case "marcas":case "proveedores_producto":return [n("codigo","Código"),n("nombre","Nombre"),n("guias","Guías","number"),n("reportes","Reportes","number")];
            case "auditoria":return [n("nombre","Menú"),n("accion","Acción"),n("modelo","Modelo"),n("estado","Diagnóstico")];
            default:return [];
        }
    }
    tableRows() {
        const source = this.state.page === "auditoria" ? this.state.audit : this.state.data?.[this.state.page];
        const term = this.state.busqueda.toLocaleLowerCase().trim();
        let rows = Array.isArray(source) ? source : [];
        if (term) rows = rows.filter(r => Object.values(r).some(v => typeof v === "string" && v.toLocaleLowerCase().includes(term)));
        const col = this.state.sort;
        if (col) rows = [...rows].sort((a,b)=> (typeof a[col] === "number" && typeof b[col] === "number") ? b[col] - a[col] : String(a[col]??"").localeCompare(String(b[col]??""),"es"));
        return rows;
    }
    trendWidth(value, key) {
        const data = this.state.data?.tendencia || [];
        const max = data.reduce((a,b)=>Math.max(a,Number(b[key])||0),0);
        return max ? (100 * (Number(value)||0)/max).toFixed(1) : 0;
    }
    quickOpen(ev) { const code=ev.currentTarget.dataset.xmlid; if (code) this.action.doAction(code); }
    exportCurrent() { this.exportTable(this.state.page === "resumen" ? "all" : this.state.page); }
    exportEverything() { this.exportTable("all"); }
    exportTable(dataset) {
        if (dataset === "auditoria") return;
        const params = new URLSearchParams({dataset,periodo:this.state.periodo,
            desde:this.state.desde,hasta:this.state.hasta,base:this.state.base,
            q: dataset === "all" ? "" : this.state.busqueda,
            sort: dataset === "all" ? "" : this.state.sort});
        window.location.assign("/transcash/dashboard/export/xlsx?" + params.toString());
    }
}
registry.category("actions").add("transcash_dashboard", TranscashDashboard);
