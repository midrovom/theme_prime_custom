/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { patch } from "@web/core/utils/patch";
import { ControlPanel } from "@web/search/control_panel/control_panel";
import { registry } from "@web/core/registry";

// ============================================================
// REGISTRO DEL SEARCH ITEM NATIVO
// ============================================================

const searchItemsRegistry = registry.category("searchItems");

searchItemsRegistry.add("ec_date_filter", {
    type: "dateFilter",
    description: "Generado el",
    fieldName: "generated_at",
    // Generador de dominio según la fecha seleccionada
    generator: (value) => {
        const start = `${value} 00:00:00`;
        const end = `${value} 23:59:59`;
        return [["generated_at", ">=", start], ["generated_at", "<=", end]];
    },
});

// ============================================================
// COMPONENTE DE UI PARA EL FILTRO
// ============================================================

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

        // Activa el search item nativo
        this.props.searchModel.toggleSearchItem("ec_date_filter", {
            generatorIds: [value],
        });

        this.state.open = false;
    }

    clear() {
        // Desactiva el search item nativo
        this.props.searchModel.deactivateSearchItem("ec_date_filter");
        this.state.date = "";
        this.state.open = false;
    }
}

// ============================================================
// PATCH DEL CONTROL PANEL PARA INYECTAR EL COMPONENTE
// ============================================================

patch(ControlPanel, {
    components: {
        ...ControlPanel.components,
        EcOnboardingDateFilter,
    },
});
