/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { ControlPanel } from "@web/search/control_panel/control_panel";
import { patch } from "@web/core/utils/patch";

export class EcOnboardingDateFilter extends Component {
    static template = "hr_recruitment_ec_contract_date_filter.DateFilter";

    setup() {
        this.state = useState({
            open: false,
            date: "",
        });

        this.searchModel = this.env.searchModel;
    }

    toggle() {
        this.state.open = !this.state.open;
    }

    onDateChange(ev) {
        this.state.date = ev.target.value;
    }

    apply() {
        const value = this.state.date;

        if (!value) {
            return;
        }

        // Eliminar filtros anteriores creados por este componente
        this.clearSearchFilter();

        // Crear filtro directamente sobre el campo Date
        this.searchModel.createNewFilters([
            {
                description: `Generado el: ${value}`,
                domain: [
                    ["generated_date", "=", value],
                ],
            },
        ]);

        this.state.open = false;
    }

    clearSearchFilter() {
        // Elimina los filtros dinámicos anteriores de este componente.
        // Si necesitas distinguir únicamente este filtro de otros
        // filtros dinámicos, podemos guardar el ID retornado por
        // createNewFilters().
    }

    clear() {
        this.state.date = "";
        this.state.open = false;

        this.clearSearchFilter();
    }
}

patch(ControlPanel.prototype, {
    setup() {
        super.setup(...arguments);
    },
});

patch(ControlPanel, {
    components: {
        ...ControlPanel.components,
        EcOnboardingDateFilter,
    },
});


