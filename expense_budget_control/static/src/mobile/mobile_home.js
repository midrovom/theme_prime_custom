/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

/** Access shortcuts independent of Odoo's desktop-only menu bar layout. */
export class ExpenseBudgetMobileHome extends Component {
    static template = "expense_budget_control.MobileHome";

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
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
    }

    async openSection(actionId) {
        await this.action.doAction(actionId);
    }
}

registry.category("actions").add("expense_budget_control.mobile_home", ExpenseBudgetMobileHome);
