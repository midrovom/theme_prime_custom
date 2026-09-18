/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { patch } from "@web/core/utils/patch";
import { ControlPanel } from "@web/search/control_panel/control_panel";

export class EcOnboardingDateFilter extends Component {
    static template = "hr_recruitment_ec_contract_date_filter.DateFilter";

    setup() {
        this.state = useState({
            open: false,
            date: "",
        });
    }

    toggle() {
        this.state.open = !this.state.open;
    }

    onDateChange(ev) {
        this.state.date = ev.target.value;
    }

    apply() {
        const value = this.state.date;
        if (!value) return;

        const [year, month, day] = value.split("-").map(Number);

        const startDate = `${value} 00:00:00`;
        const nextDate = new Date(year, month - 1, day + 1);
        const endDate = `${nextDate.getFullYear()}-${String(nextDate.getMonth() + 1).padStart(2, "0")}-${String(nextDate.getDate()).padStart(2, "0")} 00:00:00`;

        const domain = [
            ["generated_at", ">=", startDate],
            ["generated_at", "<", endDate],
        ];

        if (this.props.searchModel) {
            this.props.searchModel.dispatch("updateDomain", { domain });
        }
        this.state.open = false;
    }

    clear() {
        if (this.props.searchModel) {
            this.props.searchModel.dispatch("updateDomain", { domain: [] });
        }
        this.state.date = "";
        this.state.open = false;
    }
}

patch(ControlPanel, {
    components: {
        ...ControlPanel.components,
        EcOnboardingDateFilter,
    },
});
