/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { ControlPanel } from "@web/search/control_panel/control_panel";
import { patch } from "@web/core/utils/patch";
import { registry } from "@web/core/registry";


// ============================================================
// SEARCH ITEM
// ============================================================

const searchItemsRegistry = registry.category("searchItems");

searchItemsRegistry.add(
    "ec_date_filter",
    {
        type: "filter",
        description: "Generado el",

        /*
         * El dominio se genera utilizando el valor
         * que nosotros enviamos desde toggleSearchItem().
         */
        domain: (value) => {
            if (!value) {
                return [];
            }

            return [
                ["generated_date", "=", value],
            ];
        },
    },
    {
        force: true,
    }
);


// ============================================================
// COMPONENTE
// ============================================================

export class EcOnboardingDateFilter extends Component {

    static template =
        "hr_recruitment_ec_contract_date_filter.DateFilter";

    setup() {

        this.state = useState({
            open: false,
            date: "",
        });

        this.searchModel = this.env.searchModel;
    }


    // ========================================================
    // ABRIR / CERRAR
    // ========================================================

    toggle() {
        this.state.open = !this.state.open;
    }


    // ========================================================
    // CAMBIO DE FECHA
    // ========================================================

    onDateChange(ev) {
        this.state.date = ev.target.value;
    }


    // ========================================================
    // APLICAR
    // ========================================================

    apply() {

        const value = this.state.date;

        if (!value) {
            return;
        }

        /*
         * Si ya existe un filtro anterior,
         * primero lo desactivamos.
         */
        this.searchModel.deactivateSearchItem(
            "ec_date_filter"
        );

        /*
         * Activamos el SearchItem correctamente.
         *
         * generatorIds debe contener el valor que
         * utilizará nuestro domain().
         */
        this.searchModel.toggleSearchItem(
            "ec_date_filter",
            {
                generatorIds: [value],
            }
        );

        this.state.open = false;
    }


    // ========================================================
    // LIMPIAR
    // ========================================================

    clear() {

        /*
         * Desactiva completamente el SearchItem.
         *
         * Esto elimina el dominio:
         *
         * generated_date = fecha
         */
        this.searchModel.deactivateSearchItem(
            "ec_date_filter"
        );

        this.state.date = "";
        this.state.open = false;
    }
}


// ============================================================
// CONTROL PANEL
// ============================================================

patch(ControlPanel, {

    components: {
        ...ControlPanel.components,
        EcOnboardingDateFilter,
    },

});



