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
        domain: () => [],
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
    // APLICAR FILTRO
    // ========================================================

    apply() {

        const value = this.state.date;

        if (!value) {
            return;
        }

        // Primero limpiar cualquier filtro anterior
        this.clearFilter(false);

        /*
         * Agregamos el filtro directamente al SearchModel.
         *
         * generated_date es un campo Date, por lo que podemos
         * comparar directamente:
         *
         * generated_date = 2026-09-18
         */

        this.searchModel.toggleSearchItem(
            "ec_date_filter",
            {
                generatorIds: [value],
            }
        );

        /*
         * Cambiamos el dominio del search item.
         *
         * Esto evita trabajar con generated_at como Datetime.
         */

        const searchItem =
            this.searchModel.getSearchItems(
                "ec_date_filter"
            )[0];

        if (searchItem) {
            searchItem.domain = [
                ["generated_date", "=", value]
            ];
        }

        this.state.open = false;
    }


    // ========================================================
    // LIMPIAR
    // ========================================================

    clear(closePopup = true) {

        this.clearFilter(closePopup);

        this.state.date = "";
    }


    // ========================================================
    // ELIMINAR FILTRO
    // ========================================================

    clearFilter(closePopup = true) {

        /*
         * Desactivar el search item.
         *
         * Esto elimina el dominio aplicado.
         */

        try {
            this.searchModel.deactivateSearchItem(
                "ec_date_filter"
            );
        } catch (error) {
            console.warn(
                "No se pudo desactivar el filtro de fecha",
                error
            );
        }

        /*
         * Limpiamos cualquier filtro temporal
         * relacionado con este componente.
         */

        if (closePopup) {
            this.state.open = false;
        }
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

