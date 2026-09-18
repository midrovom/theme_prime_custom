/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { ControlPanel } from "@web/search/control_panel/control_panel";
import { patch } from "@web/core/utils/patch";

export class EcOnboardingDateFilter extends Component {
    static template =
        "hr_recruitment_ec_contract_date_filter.DateFilter";

    setup() {
        this.state = useState({
            open: false,
            date: "",
        });

        this.searchModel = this.env.searchModel;

        // Guardamos el filtro creado por nuestro componente
        this.dateFilter = null;
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

        // =====================================================
        // ELIMINAR FILTRO ANTERIOR
        // =====================================================

        this.clearSearchFilter();

        // =====================================================
        // CREAR NUEVO FILTRO
        // =====================================================

        const filters = this.searchModel.createNewFilters([
            {
                description: `Generado el: ${value}`,
                domain: [
                    ["generated_date", "=", value],
                ],
            },
        ]);

        // Guardamos referencia al filtro creado
        if (filters && filters.length) {
            this.dateFilter = filters[0];
        }

        console.log(
            "[EC DATE FILTER] Filtro aplicado:",
            value
        );

        console.log(
            "[EC DATE FILTER] Filtro creado:",
            this.dateFilter
        );

        this.state.open = false;
    }

    clearSearchFilter() {
        if (!this.dateFilter) {
            console.log(
                "[EC DATE FILTER] No existe filtro para eliminar"
            );
            return;
        }

        console.log(
            "[EC DATE FILTER] Eliminando filtro:",
            this.dateFilter
        );

        try {
            /*
             * Elimina el filtro creado mediante
             * createNewFilters().
             */
            this.searchModel.deleteNewFilter(
                this.dateFilter
            );
        } catch (error) {
            console.error(
                "[EC DATE FILTER] Error eliminando filtro:",
                error
            );
        }

        this.dateFilter = null;
    }

    clear() {
        console.log(
            "[EC DATE FILTER] Limpiando filtro de fecha"
        );

        // Eliminar filtro del SearchModel
        this.clearSearchFilter();

        // Limpiar input
        this.state.date = "";

        // Cerrar popup
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


