/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";


export class EcOnboardingDateFilter extends Component {

    static template =
        "hr_recruitment_ec_contract_date_filter.DateFilter";


    setup() {

        this.searchModel = useService("search");

        this.state = useState({
            open: false,
            date: null,
        });

    }


    toggle() {

        this.state.open = !this.state.open;

    }


    close() {

        this.state.open = false;

    }


    async onDateChange(ev) {

        const value = ev.target.value;

        if (!value) {

            await this.clear();

            return;
        }


        this.state.date = value;

        await this.applyDateFilter(value);

    }


    async applyDateFilter(value) {

        /*
         * Fecha inicial.
         *
         * Ejemplo:
         *
         * 2026-09-17 00:00:00
         */

        const startDate = `${value} 00:00:00`;


        /*
         * Calculamos el día siguiente.
         *
         * Esto permite buscar todo el día seleccionado
         * sin importar la hora de generated_at.
         */

        const [year, month, day] = value
            .split("-")
            .map(Number);


        const nextDate = new Date(
            year,
            month - 1,
            day
        );


        nextDate.setDate(
            nextDate.getDate() + 1
        );


        const nextYear = nextDate
            .getFullYear()
            .toString()
            .padStart(4, "0");


        const nextMonth = (nextDate
            .getMonth() + 1)
            .toString()
            .padStart(2, "0");


        const nextDay = nextDate
            .getDate()
            .toString()
            .padStart(2, "0");


        const endDate =
            `${nextYear}-${nextMonth}-${nextDay} 00:00:00`;


        /*
         * Dominio:
         *
         * generated_at >= día seleccionado
         * generated_at < día siguiente
         */

        const domain = [
            ["generated_at", ">=", startDate],
            ["generated_at", "<", endDate],
        ];


        /*
         * Aplicamos el dominio.
         */

        await this.env.searchModel.setDomain(domain);

    }


    async clear() {

        this.state.date = null;

        await this.env.searchModel.setDomain([]);

    }

}


registry.category("view_widgets").add(
    "ec_onboarding_date_filter",
    {
        component: EcOnboardingDateFilter,
    }
);