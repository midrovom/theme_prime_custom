/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { patch } from "@web/core/utils/patch";
import { ControlPanel } from "@web/search/control_panel/control_panel";


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
     * Abrir / cerrar el filtro
     */
    toggle() {

        this.state.open = !this.state.open;

    }


    /**
     * Cerrar el filtro
     */
    close() {

        this.state.open = false;

    }


    /**
     * Seleccionar fecha
     */
    onDateChange(ev) {

        this.state.date = ev.target.value;

    }

    /**
     * Aplicar filtro por día
     */
    apply() {
        const value = this.state.date;
        if (!value) return;

        const searchModel = this.props.searchModel;
        if (!searchModel) {
            console.error("EC Date Filter: SearchModel no disponible");
            return;
        }

        const startDate = `${value} 00:00:00`;

        const [year, month, day] = value.split("-").map(Number);
        const nextDate = new Date(year, month - 1, day);
        nextDate.setDate(nextDate.getDate() + 1);

        const nextYear = String(nextDate.getFullYear()).padStart(4, "0");
        const nextMonth = String(nextDate.getMonth() + 1).padStart(2, "0");
        const nextDay = String(nextDate.getDate()).padStart(2, "0");
        const endDate = `${nextYear}-${nextMonth}-${nextDay} 00:00:00`;

        const domain = [
            ["generated_at", ">=", startDate],
            ["generated_at", "<", endDate],
        ];

        console.log("EC Date Filter - Dominio:", domain);

        // Odoo 18: usar addDomain con global:true
        searchModel.addDomain(domain, { global: true });

        this.state.open = false;
    }

    /**
     * Limpiar filtro
     */
    clear() {
        const searchModel = this.props.searchModel;
        if (!searchModel) {
            console.error("EC Date Filter: SearchModel no disponible");
            return;
        }

        // Odoo 18: limpiar dominios globales
        searchModel.clearGlobalDomain();

        this.state.date = "";
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