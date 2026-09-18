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

        this.env.services.action.doAction("hr_recruitment_ec_contract.action_hr_ec_onboarding_package", {
            additional_context: { search_default_domain: domain },
        });

        this.state.open = false;
    }

    clear() {
        this.env.services.action.doAction("hr_recruitment_ec_contract.action_hr_ec_onboarding_package", {
            additional_context: { search_default_domain: [] },
        });
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
