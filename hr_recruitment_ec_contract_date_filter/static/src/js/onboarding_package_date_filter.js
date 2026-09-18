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

        this.env.services.action.doAction(
            "hr_recruitment_ec_contract.action_hr_ec_onboarding_package",
            {
                additional_context: {
                    filter_date: value,   // 👉 se pasa al backend
                },
                replace_last_action: true,
            }
        );

        this.state.open = false;
    }

    clear() {
        this.env.services.action.doAction(
            "hr_recruitment_ec_contract.action_hr_ec_onboarding_package",
            {
                additional_context: {
                    filter_date: false,   // 👉 sin filtro, muestra todo
                },
                replace_last_action: true,
            }
        );
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
