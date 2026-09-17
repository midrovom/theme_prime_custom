/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { ControlPanel } from "@web/search/control_panel/control_panel";
import { useState } from "@odoo/owl";

patch(ControlPanel.prototype, {
    setup() {
        super.setup(...arguments);

        this.dateFilterState = useState({
            open: false,
            date: null,
        });
    },

    toggleDateFilter() {
        this.dateFilterState.open =
            !this.dateFilterState.open;
    },

    async onDateFilterChange(ev) {
        const value = ev.target.value;

        if (!value) {
            await this.clearDateFilter();
            return;
        }

        this.dateFilterState.date = value;

        const startDate = `${value} 00:00:00`;

        const date = new Date(`${value}T00:00:00`);
        date.setDate(date.getDate() + 1);

        const nextDate = date.toISOString().slice(0, 10);

        const endDate = `${nextDate} 00:00:00`;

        /*
         * Aquí aplicamos el dominio.
         */
        this.env.searchModel.setDomain([
            ["generated_at", ">=", startDate],
            ["generated_at", "<", endDate],
        ]);
    },

    async clearDateFilter() {
        this.dateFilterState.date = null;

        this.env.searchModel.setDomain([]);
    },
});