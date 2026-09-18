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
            filterId: null,   
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
        if (!value) return;

        // Si ya existe un filtro previo, lo eliminamos
        this.clearSearchFilter();

        // Creamos el nuevo filtro y guardamos su ID
        const ids = this.searchModel.createNewFilters([
            {
                description: `Generado el: ${value}`,
                domain: [["generated_date", "=", value]],
            },
        ]);

        if (ids && ids.length) {
            this.state.filterId = ids[0];
        }

        this.state.open = false;
    }

    clearSearchFilter() {
        // Elimina el filtro creado por este componente si existe
        if (this.state.filterId) {
            this.searchModel.removeFilter(this.state.filterId);
            this.state.filterId = null;
        }
    }

    clear() {
        this.clearSearchFilter();
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

