/** @odoo-module **/

import { Component, onWillStart, onMounted, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

/** Access shortcuts independent of Odoo's desktop-only menu bar layout. */
export class ExpenseBudgetMobileHome extends Component {
    static template = "expense_budget_control.MobileHome";

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        // Mantener el menú de tarjetas solo en móviles, incluso al rotar
        // teléfonos cuya pantalla horizontal supera el ancho de 768px.
        this.isMobile = window.matchMedia("(max-width: 991.98px)").matches ||
            /Android|iPhone|iPad|iPod|Mobile/i.test(navigator.userAgent);
        this.state = useState({ loading: true, entries: [], error: "" });
        onWillStart(async () => {
            try {
                this.state.entries = await this.orm.call(
                    "expense.budget.dashboard", "get_mobile_navigation", []
                );
            } catch (error) {
                this.state.error = error.message || "No fue posible cargar los accesos.";
            } finally {
                this.state.loading = false;
            }
        });
        onMounted(() => {
            if (!this.isMobile && !this.state.error && this.state.entries.length) {
                // En escritorio entrar directamente en una sección real,
                // respetando el mismo control de roles del servidor.
                this.action.doAction(this.state.entries[0].id);
            }
        });
    }

    async openSection(actionId) {
        await this.action.doAction(actionId);
    }
}

registry.category("actions").add("expense_budget_control.mobile_home", ExpenseBudgetMobileHome);
