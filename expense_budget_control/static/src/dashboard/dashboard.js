/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
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
        this.state = useState({
            loading: true,
            error: "",
            data: { companies: [], years: [], accounts: [], categories: [], month_names: [] },
            companyId: "",
            year: "",
            categoryId: "",
            accountId: "",
            selectedMonth: -1,
        });
        onWillStart(() => this.load());
    }

    async load(companyId = this.state.companyId, year = this.state.year) {
        this.state.loading = true;
        this.state.error = "";
        try {
            const data = await this.orm.call(
                "expense.budget.dashboard", "get_dashboard_data", [companyId || false, year || false]
            );
            this.state.data = data;
            this.state.companyId = String(data.company_id || "");
            this.state.year = String(data.year || "");
            this.state.categoryId = "";
            this.state.accountId = "";
            this.state.selectedMonth = -1;
        } catch (error) {
            this.state.error = error.message || "No fue posible consultar los gastos.";
        } finally {
            this.state.loading = false;
        }
    }

    onCompanyChange(event) {
        this.load(event.target.value, false);
    }

    onYearChange(event) {
        this.load(this.state.companyId, event.target.value);
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

    get monthlyAmounts() {
        const months = Array(12).fill(0);
        for (const account of this.selectedAccounts) {
            account.months.forEach((amount, index) => { months[index] += amount; });
        }
        return months;
    }

    get bars() {
        const monthly = this.monthlyAmounts;
        const max = Math.max(1, ...monthly);
        return monthly.map((amount, index) => ({
            index,
            label: this.state.data.month_names[index] || "",
            short: (this.state.data.month_names[index] || "").slice(0, 3),
            amount,
            height: `${amount > 0 ? Math.max(2, (amount / max) * 100) : 0}%`,
            active: this.state.selectedMonth === index,
            muted: this.state.selectedMonth >= 0 && this.state.selectedMonth !== index,
        }));
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

    get pieAccounts() {
        // Las proporciones comparan las cuentas del rubro en el mes filtrado.
        // En "Todos los meses" muestran el acumulado anual. Pulsar una porción
        // selecciona esa cuenta sin cambiar los valores de las otras porciones.
        const selectedMonth = this.state.selectedMonth;
        return this.categoryAccounts.map((account) => ({
            ...account,
            amount: selectedMonth < 0
                ? account.months.reduce((sum, value) => sum + value, 0)
                : account.months[selectedMonth],
        })).filter((account) => account.amount > 0).sort((a, b) => b.amount - a.amount);
    }

    get pieSlices() {
        const accounts = this.pieAccounts;
        const total = accounts.reduce((sum, account) => sum + account.amount, 0);
        if (!total) { return []; }
        let angle = -Math.PI / 2;
        return accounts.map((account, index) => {
            const share = account.amount / total;
            const start = angle;
            const end = angle + share * Math.PI * 2;
            angle = end;
            const polar = (radians) => [50 + 45 * Math.cos(radians), 50 + 45 * Math.sin(radians)];
            const [sx, sy] = polar(start);
            const [ex, ey] = polar(end);
            const largeArc = share > 0.5 ? 1 : 0;
            return {
                id: account.id,
                name: account.name,
                amount: account.amount,
                percentage: Math.round(share * 1000) / 10,
                color: COLORS[index % COLORS.length],
                path: `M 50 50 L ${sx} ${sy} A 45 45 0 ${largeArc} 1 ${ex} ${ey} Z`,
                full: accounts.length === 1,
                active: this.state.accountId === String(account.id),
            };
        });
    }

    get monthlyDetail() {
        const monthIndex = this.state.selectedMonth;
        if (monthIndex < 0) { return []; }
        return this.selectedAccounts.map((account) => ({
            id: account.id,
            name: account.name,
            amount: account.months[monthIndex],
        })).filter((item) => item.amount !== 0).sort((a, b) => b.amount - a.amount);
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
        return new Intl.NumberFormat("es-EC", { minimumFractionDigits: 2, maximumFractionDigits: 2 })
            .format(value || 0) + ` ${this.state.data.currency || ""}`;
    }
}

registry.category("actions").add("expense_budget_control.dashboard", ExpenseBudgetDashboard);
