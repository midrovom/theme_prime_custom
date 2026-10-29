/** @odoo-module **/

import { Component, onWillStart, onMounted, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

const COLORS = [
    "#167a92", "#ee9a4b", "#7b69b0", "#479b80", "#bc6684",
    "#ba9a35", "#5b85c4", "#df7474", "#4aadb2", "#9a88ce",
];

export class ExpenseBudgetDashboard extends Component {
    static template = "expense_budget_control.Dashboard";

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this._loadSerial = 0;
        this._startupRetried = false;
        this.state = useState({
            loading: true,
            ready: false,
            error: "",
            data: { companies: [], years: [], accounts: [], categories: [], cost_centers: [], breakdown: [], month_names: [], company_id: false },
            companyId: "",
            year: "",
            categoryId: "",
            accountId: "",
            costCenterId: "",
            selectedMonth: -1,
            chartType: "bar",
        });
        // Arrancar siempre con el contexto actual del servidor: en una nueva
        // pestaña/recarga aún no existen opciones de empresa/año/centro.
        // Esperar los datos antes de pintar los selectores evita valores visibles
        // que no coinciden con los filtros aplicados realmente.
        onWillStart(async () => { await this.load(false, false, false, false); });
        // Si la primera petición falló por una interrupción transitoria,
        // reintentar una sola vez una vez montada la pantalla.
        onMounted(() => {
            if (!this._startupRetried && !this.state.data.company_id) {
                this._startupRetried = true;
                void this.load(false, false, false, false);
            }
        });
    }

    async load(companyId = this.state.companyId, year = this.state.year,
               costCenterId = this.state.costCenterId, preserveFilters = true) {
        // El centro se filtra en el servidor. Al refrescar el dashboard NO se
        // deben perder los filtros combinados (rubro, cuenta y mes).
        const serial = ++this._loadSerial;
        const categoryId = preserveFilters ? this.state.categoryId : "";
        const accountId = preserveFilters ? this.state.accountId : "";
        this.state.loading = true;
        this.state.error = "";
        try {
            const data = await this.orm.call(
                "expense.budget.dashboard", "get_dashboard_data",
                [companyId || false, year || false, costCenterId || false]
            );
            // Si el usuario cambia varios filtros rápidamente, solo la última
            // respuesta puede reemplazar los datos en pantalla.
            if (serial !== this._loadSerial) { return; }
            if (!data || !Array.isArray(data.companies) || !Array.isArray(data.breakdown)) {
                throw new Error("La respuesta del dashboard no contiene los filtros y consumos esperados.");
            }
            this.state.data = data;
            this.state.companyId = String(data.company_id || "");
            this.state.year = String(data.year || "");
            this.state.costCenterId = String(data.cost_center_id || "");
            this.state.categoryId = (data.categories || []).some((row) => String(row.id) === categoryId)
                ? categoryId : "";
            this.state.accountId = (data.accounts || []).some((row) =>
                String(row.id) === accountId &&
                (!this.state.categoryId || String(row.category_id) === this.state.categoryId))
                ? accountId : "";
            if (!preserveFilters) { this.state.selectedMonth = -1; }
        } catch (error) {
            if (serial === this._loadSerial) {
                this.state.error = error.message || "No fue posible consultar los gastos.";
            }
        } finally {
            if (serial === this._loadSerial) {
                this.state.loading = false;
                this.state.ready = true;
            }
        }
    }

    openMobileHome() {
        return this.action.doAction("expense_budget_control.action_expense_budget_mobile_home");
    }

    onCompanyChange(event) {
        return this.load(event.target.value, false, false, false);
    }

    onYearChange(event) {
        return this.load(this.state.companyId, event.target.value);
    }

    onCostCenterChange(event) {
        return this.load(this.state.companyId, this.state.year, event.target.value);
    }

    onCategoryChange(event) {
        this.state.categoryId = event.target.value;
        this.state.accountId = "";
    }

    onAccountChange(event) {
        this.state.accountId = event.target.value;
    }

    onMonthChange(event) {
        const month = Number(event.target.value);
        this.state.selectedMonth = Number.isInteger(month) && month >= 0 && month < 12 ? month : -1;
    }

    onChartTypeChange(event) {
        this.state.chartType = event.target.value === "pie" ? "pie" : "bar";
    }

    toggleAccount(accountId) {
        const next = String(accountId);
        this.state.accountId = this.state.accountId === next ? "" : next;
    }

    selectMonth(monthIndex) {
        this.state.selectedMonth = this.state.selectedMonth === monthIndex ? -1 : monthIndex;
    }

    get categoryAccounts() {
        return this.state.data.accounts.filter((account) =>
            !this.state.categoryId || String(account.category_id) === this.state.categoryId
        );
    }

    get selectedAccounts() {
        return this.categoryAccounts.filter((account) =>
            !this.state.accountId || String(account.id) === this.state.accountId
        );
    }

    get filteredBreakdown() {
        // El servidor entrega filas por centro/rubro/cuenta/mes. Esta es la
        // misma fuente para el total, las barras, el pastel y el detalle.
        return (this.state.data.breakdown || []).filter((row) =>
            (!this.state.categoryId || String(row.category_id) === this.state.categoryId) &&
            (!this.state.accountId || String(row.account_id) === this.state.accountId)
        );
    }

    get monthlyAmounts() {
        const months = Array(12).fill(0);
        for (const row of this.filteredBreakdown) {
            row.months.forEach((amount, index) => { months[index] += Number(amount || 0); });
        }
        return months;
    }

    get chartByCenter() {
        // Con Todos los centros se muestra la distribución por centro;
        // al elegir un centro, el desglose pasa a sus cuentas controladas.
        return !this.state.costCenterId;
    }

    get chartGroups() {
        const groups = new Map();
        const byCenter = this.chartByCenter;
        const month = this.state.selectedMonth;
        for (const row of this.filteredBreakdown) {
            const id = String(byCenter ? row.center_id : row.account_id);
            const name = byCenter ? row.center_name : row.account_name;
            const amount = month < 0
                ? row.months.reduce((total, item) => total + Number(item || 0), 0)
                : Number(row.months[month] || 0);
            if (!groups.has(id)) { groups.set(id, {id, name, amount: 0}); }
            groups.get(id).amount += amount;
        }
        return [...groups.values()].sort((a, b) => b.amount - a.amount ||
            a.name.localeCompare(b.name) || a.id.localeCompare(b.id));
    }


    get monthlyCenterGroups() {
        // Doce grupos fijos (enero a diciembre), y dentro de cada mes una
        // columna por centro de costo incluido en la combinación de filtros.
        // El pastel conserva chartGroups: total anual/mensual por centro o cuenta.
        const groups = new Map();
        for (const row of this.filteredBreakdown) {
            const id = String(row.center_id);
            if (!groups.has(id)) {
                groups.set(id, {
                    id,
                    name: row.center_name || "Sin centro de costo",
                    months: Array(12).fill(0),
                });
            }
            const center = groups.get(id);
            for (let monthIndex = 0; monthIndex < 12; monthIndex++) {
                center.months[monthIndex] += Number(row.months[monthIndex] || 0);
            }
        }
        const centers = [...groups.values()].sort((a, b) =>
            a.name.localeCompare(b.name, "es") || a.id.localeCompare(b.id));
        // Si solo se visualiza un centro, el nombre aparece una sola vez en
        // la descripción de la gráfica y no encima de los doce meses.
        const showCenterNames = !this.state.costCenterId && centers.length > 1;
        // La misma escala para los 12 meses, para comparar importes reales.
        const maximum = Math.max(1, ...centers.flatMap(center =>
            center.months.map(amount => Math.abs(amount))));
        return Array.from({length: 12}, (_, index) => ({
            index,
            name: this.state.data.month_names[index] || "",
            short: (this.state.data.month_names[index] || "").slice(0, 3),
            active: this.state.selectedMonth === index,
            muted: this.state.selectedMonth >= 0 && this.state.selectedMonth !== index,
            showCenterNames,
            centers: centers.map(center => {
                const amount = center.months[index];
                return {
                    id: center.id,
                    name: center.name,
                    amount,
                    // Nombres completos en pantalla, sin códigos abreviados.
                    height: `${amount ? Math.max(2, Math.abs(amount) / maximum * 100) : 0}%`,
                    negative: amount < 0,
                    selected: this.state.costCenterId === center.id,
                };
            }),
        }));
    }

    async selectMonthCenter(monthIndex, centerId) {
        // Un clic selecciona centro + mes sin borrar rubro ni cuenta controlada.
        this.state.selectedMonth = monthIndex;
        if (this.state.costCenterId !== String(centerId)) {
            await this.load(this.state.companyId, this.state.year, String(centerId));
        }
    }

    async selectChartGroup(groupId) {
        if (this.chartByCenter) {
            // Entrar al centro mediante su barra/porción sin perder rubro o mes.
            return this.load(this.state.companyId, this.state.year, groupId);
        }
        this.toggleAccount(groupId);
    }

    get accountBars() {
        if (this.state.selectedMonth < 0 || this.chartByCenter) { return []; }
        const accounts = this.accountDetail;
        const maximum = Math.max(1, ...accounts.map((account) => Math.abs(account.amount)));
        return accounts.map((account) => ({
            ...account,
            width: `${Math.abs(account.amount) / maximum * 100}%`,
            isNegative: account.amount < 0,
        }));
    }

    get accountDetail() {
        // Las cuentas del detalle y el total usan exactamente las mismas filas
        // que el gráfico, incluso cuando la cuenta existe en varios centros.
        const groups = new Map();
        const month = this.state.selectedMonth;
        for (const row of this.filteredBreakdown) {
            const id = String(row.account_id);
            const amount = month < 0
                ? row.months.reduce((total, item) => total + Number(item || 0), 0)
                : Number(row.months[month] || 0);
            if (!groups.has(id)) { groups.set(id, {id, name: row.account_name, amount: 0}); }
            groups.get(id).amount += amount;
        }
        return [...groups.values()].sort((a, b) => b.amount - a.amount || a.name.localeCompare(b.name));
    }

    get chartTitle() {
        return this.state.chartType === "bar"
            ? "Gastos por mes y centro de costo"
            : (this.chartByCenter ? "Gastos por centro de costo" : "Gastos por cuenta controlada");
    }

    get chartHint() {
        if (this.state.chartType === "bar") {
            // El nombre se muestra aquí una sola vez si hay un único centro.
            const firstMonth = this.monthlyCenterGroups[0];
            if (firstMonth?.centers.length === 1) {
                return `Centro: ${firstMonth.centers[0].name} · Consumo por mes según los filtros seleccionados.`;
            }
            return "En cada mes se muestra una barra por centro según los filtros seleccionados.";
        }
        return `Consumos de ${this.periodName.toLowerCase()} · ${this.state.year} · según los filtros seleccionados`;
    }

    get totalSpent() {
        const monthly = this.monthlyAmounts;
        return this.state.selectedMonth < 0
            ? monthly.reduce((sum, value) => sum + value, 0)
            : monthly[this.state.selectedMonth];
    }

    get peak() {
        const monthly = this.monthlyAmounts;
        const maximum = Math.max(0, ...monthly);
        const index = monthly.indexOf(maximum);
        return {
            name: maximum > 0 ? this.state.data.month_names[index] : "—",
            amount: maximum,
        };
    }

    get pieSlices() {
        const groups = this.chartGroups;
        // Un pastel no puede representar una participación negativa de forma
        // correcta. No ocultar reversiones para fabricar un 100% incorrecto.
        if (groups.some((group) => group.amount < 0)) { return []; }
        const total = groups.reduce((sum, group) => sum + group.amount, 0);
        if (total <= 0) { return []; }
        const positive = groups.filter((group) => group.amount > 0);
        // Las etiquetas muestran décimas porcentuales y deben sumar 100,0%.
        // Se distribuye el residuo de redondeo, no se modifica ningún importe.
        const raw = positive.map((group) => group.amount / total * 1000);
        const units = raw.map((value) => Math.floor(value));
        let remaining = 1000 - units.reduce((sum, value) => sum + value, 0);
        const order = raw.map((value, index) => ({index, remainder: value - units[index]}))
            .sort((a, b) => b.remainder - a.remainder || a.index - b.index);
        for (let i = 0; i < remaining; i++) { units[order[i % order.length].index] += 1; }
        let angle = -Math.PI / 2;
        return positive.map((group, index) => {
            const share = group.amount / total;
            const start = angle;
            const end = angle + share * Math.PI * 2;
            angle = end;
            const polar = (radians) => [50 + 45 * Math.cos(radians), 50 + 45 * Math.sin(radians)];
            const [sx, sy] = polar(start);
            const [ex, ey] = polar(end);
            const largeArc = share > 0.5 ? 1 : 0;
            return {
                id: group.id,
                name: group.name,
                amount: group.amount,
                percentage: units[index] / 10,
                color: COLORS[(this.chartByCenter
                    ? (this.state.data.cost_centers || []).findIndex((c) => String(c.id) === group.id)
                    : (this.state.data.accounts || []).findIndex((a) => String(a.id) === group.id)
                ) % COLORS.length] || COLORS[0],
                path: `M 50 50 L ${sx} ${sy} A 45 45 0 ${largeArc} 1 ${ex} ${ey} Z`,
                full: positive.length === 1,
                active: !this.chartByCenter && this.state.accountId === group.id,
            };
        });
    }

    get pieEmptyMessage() {
        return this.chartGroups.some((group) => group.amount < 0)
            ? "Hay consumos negativos; no es posible mostrar porcentajes fiables en un pastel."
            : "No hay gastos para distribuir con los filtros elegidos.";
    }

    get periodName() {
        return this.state.selectedMonth < 0 ? "Todos los meses" :
            this.state.data.month_names[this.state.selectedMonth];
    }

    get totalSpentLabel() {
        return this.state.selectedMonth < 0 ? "Gasto acumulado del año" :
            `Gasto en ${this.periodName}`;
    }

    get scopeName() {
        if (this.state.accountId) {
            return this.selectedAccounts[0]?.name || "Cuenta controlada";
        }
        if (this.state.categoryId) {
            return this.state.data.categories.find((c) => String(c.id) === this.state.categoryId)?.name || "Rubro";
        }
        return "Gasto global";
    }

    formatMoney(value) {
        const minDigits = this.state.data?.decimal_digits ?? 2;
        return new Intl.NumberFormat("es-EC", { minimumFractionDigits: minDigits, maximumFractionDigits: 12 })
            .format(value || 0) + ` ${this.state.data.currency || ""}`;
    }
}

registry.category("actions").add("expense_budget_control.dashboard", ExpenseBudgetDashboard);
