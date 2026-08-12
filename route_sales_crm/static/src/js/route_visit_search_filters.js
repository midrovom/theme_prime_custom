/** @odoo-module **/

import { registry } from "@web/core/registry";

const { date } = luxon;

function todayDomain() {
    const start = date.now().startOf("day").toISO();
    const end = date.now().endOf("day").toISO();
    return [["planned_at", ">=", start], ["planned_at", "<=", end]];
}

registry.category("search_filters").add("route_visit_today", {
    description: "Hoy",
    domain: todayDomain,
});
