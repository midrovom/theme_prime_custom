/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { patch } from "@web/core/utils/patch";
import { ControlPanel } from "@web/search/control_panel/control_panel";


/**
 * ============================================================
 * COMPONENTE DEL FILTRO
 * ============================================================
 */

export class EcOnboardingDateFilter extends Component {

    static template =
        "hr_recruitment_ec_contract_date_filter.DateFilter";


    setup() {

        this.state = useState({
            open: false,
            date: "",
        });

    }


    /**
     * Abrir / cerrar calendario
     */
    toggle() {

        this.state.open = !this.state.open;

    }


    /**
     * Cerrar popup
     */
    close() {

        this.state.open = false;

    }


    /**
     * Cuando el usuario selecciona una fecha
     */
    onDateChange(ev) {

        const value = ev.target.value;

        if (!value) {
            return;
        }

        this.state.date = value;

    }


    /**
     * Aplicar filtro
     */
    apply() {

        const value = this.state.date;

        if (!value) {
            return;
        }


        /*
         * Obtenemos el SearchModel del ControlPanel.
         */
        const searchModel = this.props.searchModel;


        if (!searchModel) {

            console.error(
                "EC Date Filter: SearchModel no disponible"
            );

            return;

        }


        /*
         * =====================================================
         * FECHA INICIAL
         * =====================================================
         *
         * Ejemplo:
         *
         * 2026-09-17 00:00:00
         */

        const startDate =
            `${value} 00:00:00`;


        /*
         * =====================================================
         * FECHA FINAL
         * =====================================================
         *
         * Tomamos el día siguiente.
         */

        const [year, month, day] =
            value.split("-").map(Number);


        const nextDate = new Date(
            year,
            month - 1,
            day
        );


        nextDate.setDate(
            nextDate.getDate() + 1
        );


        const nextYear =
            String(nextDate.getFullYear())
                .padStart(4, "0");


        const nextMonth =
            String(nextDate.getMonth() + 1)
                .padStart(2, "0");


        const nextDay =
            String(nextDate.getDate())
                .padStart(2, "0");


        const endDate =
            `${nextYear}-${nextMonth}-${nextDay} 00:00:00`;


        /*
         * =====================================================
         * DOMINIO
         * =====================================================
         */

        const domain = [
            ["generated_at", ">=", startDate],
            ["generated_at", "<", endDate],
        ];


        console.log(
            "EC Date Filter - Aplicando:",
            domain
        );


        /*
         * =====================================================
         * APLICAR AL SEARCH MODEL
         * =====================================================
         */

        searchModel.setDomain(domain);


        /*
         * Cerramos popup
         */

        this.state.open = false;

    }


    /**
     * Limpiar filtro
     */
    clear() {

        this.state.date = "";


        const searchModel =
            this.props.searchModel;


        if (!searchModel) {
            return;
        }


        searchModel.setDomain([]);


        this.state.open = false;

    }

}


/**
 * ============================================================
 * REGISTRAR COMPONENTE EN CONTROL PANEL
 * ============================================================
 */

patch(ControlPanel, {

    components: {
        ...ControlPanel.components,
        EcOnboardingDateFilter,
    },

});