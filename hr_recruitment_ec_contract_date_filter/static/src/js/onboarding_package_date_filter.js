/** @odoo-module **/

// import { Component, useState } from "@odoo/owl";
// import { patch } from "@web/core/utils/patch";
// import { ControlPanel } from "@web/search/control_panel/control_panel";
// import { rpc } from "@web/core/network/rpc";

// export class EcOnboardingDateFilter extends Component {
//     static template = "hr_recruitment_ec_contract_date_filter.DateFilter";

//     setup() {
//         this.state = useState({
//             open: false,
//             date: "",
//         });
//     }

//     toggle() {
//         this.state.open = !this.state.open;
//     }

//     onDateChange(ev) {
//         this.state.date = ev.target.value;
//     }

//     async apply() {
//         const value = this.state.date;
//         if (!value) return;

//         const start = `${value} 00:00:00`;
//         const end = `${value} 23:59:59`;

//         try {
//             // Refrescar la vista con dominio dinámico
//             await this.env.services.action.doAction({
//                 type: "ir.actions.act_window",
//                 res_model: "hr.ec.onboarding.package",
//                 views: [[false, "list"], [false, "form"]],
//                 domain: [
//                     ["generated_at", ">=", start],
//                     ["generated_at", "<=", end],
//                 ],
//             });
//         } catch (err) {
//             console.error("Error al aplicar filtro:", err);
//         }

//         this.state.open = false;
//     }

//     async clear() {
//         try {
//             // Refrescar la vista sin dominio (todos los registros)
//             await this.env.services.action.doAction({
//                 type: "ir.actions.act_window",
//                 res_model: "hr.ec.onboarding.package",
//                 views: [[false, "list"], [false, "form"]],
//                 domain: [],
//             });
//         } catch (err) {
//             console.error("Error al limpiar:", err);
//         }

//         this.state.date = "";
//         this.state.open = false;
//     }
// }

// patch(ControlPanel, {
//     components: {
//         ...ControlPanel.components,
//         EcOnboardingDateFilter,
//     },
// });

/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { patch } from "@web/core/utils/patch";
import { ControlPanel } from "@web/search/control_panel/control_panel";

export class EcOnboardingDateFilter extends Component {
    static template = "hr_recruitment_ec_contract_date_filter.DateFilter";

    setup() {
        this.state = useState({
            date: "",
        });
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

        // Aquí aplicamos el mismo domain que pondrías en XML
        this.env.searchModel.dispatch("updateDomain", { domain });
    }

    clear() {
        this.env.searchModel.dispatch("updateDomain", { domain: [] });
        this.state.date = "";
    }
}

patch(ControlPanel, {
    components: {
        ...ControlPanel.components,
        EcOnboardingDateFilter,
    },
});


