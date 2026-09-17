// /** @odoo-module **/

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

//         try {
//             const ids = await rpc("/hr_ec_onboarding/filter_by_date", {
//                 date_str: value,
//             });

//             // Refrescar la vista lista estándar con dominio
//             this.env.services.action.doAction({
//                 type: "ir.actions.act_window",
//                 res_model: "hr.ec.onboarding.package",
//                 views: [[false, "list"], [false, "form"]],
//                 domain: [["id", "in", ids]],
//             });
//         } catch (err) {
//             console.error("Error al consultar:", err);
//         }

//         this.state.open = false;
//     }

//     async clear() {
//         try {
//             const ids = await rpc("/hr_ec_onboarding/filter_by_date", {
//                 date_str: "",
//             });

//             this.env.services.action.doAction({
//                 type: "ir.actions.act_window",
//                 res_model: "hr.ec.onboarding.package",
//                 views: [[false, "list"], [false, "form"]],
//                 domain: [["id", "in", ids]],
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
import { rpc } from "@web/core/network/rpc";

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

    async apply() {
        const value = this.state.date;
        if (!value) return;

        try {
            const ids = await rpc("/hr_ec_onboarding/filter_by_date", {
                date_str: value,
            });

            // Aplicar dominio directamente al modelo de búsqueda
            this.env.searchModel.setDomain([["id", "in", ids]]);
        } catch (err) {
            console.error("Error al consultar:", err);
        }

        this.state.open = false;
    }

    async clear() {
        try {
            const ids = await rpc("/hr_ec_onboarding/filter_by_date", {
                date_str: "",
            });

            // Limpiar el dominio y mostrar todos los registros
            this.env.searchModel.setDomain([]);
        } catch (err) {
            console.error("Error al limpiar:", err);
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

