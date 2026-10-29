/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

const COLORS = [
    "#167a92", "#ee9a4b", "#7b69b0", "#479b80", "#bc6684",
    "#ba9a35", "#5b85c4", "#df7474", "#4aadb2", "#9a88ce",
];
const GROUP_LABELS = {
    center: "centro de costo",
    category: "rubro",
    account: "cuenta controlada",
    month: "mes",
};

export class ExpenseBudgetDashboard extends Component {
    static template = "expense_budget_control.Dashboard";

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this._loadSerial = 0;
        this.state = useState({
            loading: true,
            error: "",
            data: { companies: [], years: [], accounts: [], categories: [], cost_centers: [], breakdown: [], month_names: [] },
            companyId: "",
            year: "",
            categoryId: "",
            accountId: "",
            costCenterId: "",
            selectedMonth: -1,
            chartType: "bar",
            chartGroup: "center",
        });
        onWillStart(() => this.load());
    }

    async load(companyId = this.state.companyId, year = this.state.year,
               costCenterId = this.state.costCenterId, preserveFilters = true) {
        const serial = ++this._loadSerial;
        const previousCategory = preserveFilters ? this.state.categoryId : "";
        const previousAccount = preserveFilters ? this.state.accountId : "";
        this.state.loading = true;
        this.state.error = "";
        try {
            const data = await this.orm.call(
                "expense.budget.dashboard", "get_dashboard_data",
                [companyId || false, year || false, costCenterId || false]
            );
            if (serial !== this._loadSerial) { return; }
            this.state.data = data;
            this.state.companyId = String(data.company_id || "");
            this.state.year = String(data.year || "");
            this.state.costCenterId = String(data.cost_center_id || "");
            this.state.categoryId = (data.categories || []).some((category) => String(category.id) === previousCategory)
                ? previousCategory : "";
            this.state.accountId = (data.accounts || []).some((account) =>
                String(account.id) === previousAccount &&
                (!this.state.categoryId || String(account.category_id) === this.state.categoryId))
                ? previousAccount : "";
            if (!preserveFilters) { this.state.selectedMonth = -1; }
        } catch (error) {
            if (serial === this._loadSerial) {
                this.state.error = error.message || "No fue posible consultar los gastos.";
            }
        } finally {
            if (serial === this._loadSerial) { this.state.loading = false; }
        }
    }

    openMobileHome() {
        return this.action.doAction("expense_budget_control.action_expense_budget_mobile_home");
    }

    onCompanyChange(event) {
        this.state.chartGroup = "center";
        this.load(event.target.value, false, false, false);
    }

    onYearChange(event) {
        this.load(this.state.companyId, event.target.value);
    }

    onCostCenterChange(event) {
        const centerId = event.target.value;
        // Con Todos los centros, mostrar cuál consume más; al elegir uno,
        // mostrar primero la distribución de sus cuentas dentro del centro.
        this.state.chartGroup = centerId ? "account" : "center";
        this.load(this.state.companyId, this.state.year, centerId);
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

    onChartGroupChange(event) {
        this.state.chartGroup = Object.hasOwn(GROUP_LABELS, event.target.value)
            ? event.target.value : "center";
    }

    toggleAccount(accountId) {
        const next = String(accountId);
        this.state.accountId = this.state.accountId === next ? "" : next;
    }

    selectMonth(monthIndex) {
        this.state.selectedMonth = this.state.selectedMonth === monthIndex ? -1 : monthIndex;
    }

    onDistributionSelect(item) {
        if (this.state.chartGroup === "month") {
            this.selectMonth(Number(item.id));
        } else if (this.state.chartGroup === "center") {
            const id = String(item.id);
            this.state.chartGroup = this.state.costCenterId === id ? "center" : "account";
            this.load(this.state.companyId, this.state.year, this.state.costCenterId === id ? false : id);
        } else if (this.state.chartGroup === "category") {
            const id = String(item.id);
            this.state.categoryId = this.state.categoryId === id ? "" : id;
            this.state.accountId = "";
        } else {
            this.toggleAccount(item.id);
        }
    }

    get categoryAccounts() {
        return (this.state.data.accounts || []).filter((account) =>
            !this.state.categoryId || String(account.category_id) === this.state.categoryId
        );
    }

    get selectedAccounts() {
        return this.categoryAccounts.filter((account) =>
            !this.state.accountId || String(account.id) === this.state.accountId
        );
    }

    get selectedBreakdown() {
        // get_dashboard_data() ya ha filtrado por empresa/año/centro y ACL.
        // Aplicamos rubro y cuenta a LAS MISMAS filas que usan las dos gráficas.
        return (this.state.data.breakdown || []).filter((item) =>
            (!this.state.categoryId || String(item.category_id) === this.state.categoryId) &&
            (!this.state.accountId || String(item.account_id) === this.state.accountId)
        );
    }

    get monthlyAmounts() {
        const months = Array(12).fill(0);
        for (const row of this.selectedBreakdown) {
            row.months.forEach((amount, index) => { months[index] += Number(amount || 0); });
        }
        return months;
    }

    get distributionRows() {
        const month = this.state.selectedMonth;
        const group = this.state.chartGroup;
        const amounts = new Map();
        for (const row of this.selectedBreakdown) {
            if (group === "month") {
                row.months.forEach((value, index) => {
                    if (month >= 0 && index !== month) { return; }
                    const key = String(index);
                    if (!amounts.has(key)) {
                        amounts.set(key, { id: index, name: this.state.data.month_names[index] || "", amount: 0 });
                    }
                    amounts.get(key).amount += Number(value || 0);
                });
                continue;
            }
            const id = row[`${group}_id`];
            const name = row[`${group}_name`];
            const key = String(id);
            if (!amounts.has(key)) { amounts.set(key, { id, name, amount: 0 }); }
            amounts.get(key).amount += month < 0
                ? row.months.reduce((sum, value) => sum + Number(value || 0), 0)
                : Number(row.months[month] || 0);
        }
        // Una opción de centro seleccionada sin líneas debe seguir siendo
        // visible como cero; nunca mezclarla con Todos los centros.
        if (group === "center" && this.state.costCenterId && !amounts.size) {
            const center = (this.state.data.cost_centers || []).find((c) =>
                String(c.id) === this.state.costCenterId);
            if (center) { amounts.set(String(center.id), { ...center, amount: 0 }); }
        }
        const rows = [...amounts.values()].sort((a, b) =>
            b.amount - a.amount || a.name.localeCompare(b.name));
        const positiveTotal = rows.reduce((sum, row) => sum + Math.max(0, row.amount), 0);
        const maxAbsolute = Math.max(0, ...rows.map((row) => Math.abs(row.amount)));
        return rows.map((row) => ({
            ...row,
            percentage: positiveTotal && row.amount > 0 ? (100 * row.amount / positiveTotal) : 0,
            width: maxAbsolute ? `${Math.abs(row.amount) / maxAbsolute * 100}%` : "0%",
            isNegative: row.amount < 0,
        }));
    }

    get pieSlices() {
        // Un gráfico circular solo admite valores positivos: los créditos o
        // devoluciones negativos se conservan en las barras y en el detalle.
        const rows = this.distributionRows.filter((row) => row.amount > 0);
        const total = rows.reduce((sum, row) => sum + row.amount, 0);
        if (!total) { return []; }
        let angle = -Math.PI / 2;
        return rows.map((item, index) => {
            const share = item.amount / total;
            const start = angle;
            const end = angle + share * Math.PI * 2;
            angle = end;
            const polar = (rad) => [50 + 45 * Math.cos(rad), 50 + 45 * Math.sin(rad)];
            const [sx, sy] = polar(start);
            const [ex, ey] = polar(end);
            return {
                ...item,
                percentage: Math.round(share * 10000) / 100,
                color: COLORS[index % COLORS.length],
                path: `M 50 50 L ${sx} ${sy} A 45 45 0 ${share > .5 ? 1 : 0} 1 ${ex} ${ey} Z`,
                full: rows.length === 1,
                active: (this.state.chartGroup === "center" && this.state.costCenterId === String(item.id)) ||
                    (this.state.chartGroup === "category" && this.state.categoryId === String(item.id)) ||
                    (this.state.chartGroup === "account" && this.state.accountId === String(item.id)) ||
                    (this.state.chartGroup === "month" && this.state.selectedMonth === item.id),
            };
        });
    }

    get chartTitle() {
        return `Consumo por ${GROUP_LABELS[this.state.chartGroup]} · ${this.periodName}`;
    }

    get chartHint() {
        const center = this.selectedCenterName;
        return `Empresa y año seleccionados · ${center} · Porcentajes sobre los consumos positivos del filtro`;
    }

    get groupHeading() {
        return GROUP_LABELS[this.state.chartGroup];
    }

    get totalSpent() {
        return this.state.selectedMonth < 0
            ? this.monthlyAmounts.reduce((sum, value) => sum + value, 0)
            : this.monthlyAmounts[this.state.selectedMonth];
    }

    get peak() {
        const amounts = this.monthlyAmounts;
        const maximum = Math.max(0, ...amounts);
        return {
            name: maximum > 0 ? this.state.data.month_names[amounts.indexOf(maximum)] : "—",
            amount: maximum,
        };
    }

    get selectedCenterName() {
        if (!this.state.costCenterId) { return "Todos los centros"; }
        return (this.state.data.cost_centers || []).find((center) =>
            String(center.id) === this.state.costCenterId)?.name || "Centro de costo";
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
            return (this.state.data.categories || []).find((c) =>
                String(c.id) === this.state.categoryId)?.name || "Rubro";
        }
        return this.selectedCenterName;
    }

    formatPercent(value) {
        return new Intl.NumberFormat("es-EC", { minimumFractionDigits: 0, maximumFractionDigits: 2 })
            .format(value || 0) + "%";
    }

    formatMoney(value) {
        const minDigits = this.state.data?.decimal_digits ?? 2;
        return new Intl.NumberFormat("es-EC", { minimumFractionDigits: minDigits, maximumFractionDigits: 12 })
            .format(value || 0) + ` ${this.state.data.currency || ""}`;
    }
}

registry.category("actions").add("expense_budget_control.dashboard", ExpenseBudgetDashboard);
