/** @odoo-module **/

import { Component, onWillUnmount, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

export class CensusCustomerLookupField extends Component {
    static template = "conedera_odoo_census.CensusCustomerLookupField";
    static props = { ...standardFieldProps };

    setup() {
        this.orm = useService("orm");
        this.state = useState({
            query: this.props.record.data[this.props.name] || "",
            loading: false,
            results: [],
            open: false,
            searched: false,
        });
        this.timer = null;
        this.requestSerial = 0;
        onWillUnmount(() => {
            if (this.timer) {
                clearTimeout(this.timer);
            }
        });
    }

    get selectedId() {
        return this.props.record.data.selected_partner_ref_id;
    }

    statusClass(status) {
        if (status === "own_census" || status === "team_census") {
            return "text-bg-success";
        }
        if (status === "available_contact") {
            return "text-bg-info";
        }
        if (status === "other_census" || status === "assigned_contact") {
            return "text-bg-warning";
        }
        return "text-bg-secondary";
    }

    async onInput(ev) {
        const query = ev.target.value;
        this.state.query = query;
        this.state.open = true;
        this.state.searched = false;
        await this.props.record.update({
            [this.props.name]: query,
            selected_partner_ref_id: false,
            selected_candidate_status: false,
            selected_can_open: false,
            selected_can_use: false,
            selected_can_request_reassignment: false,
            selected_is_census: false,
            existing_partner_id: false,
            existing_name: false,
            existing_vat: false,
            existing_commercial_name: false,
            existing_phone: false,
            existing_mobile: false,
            existing_email: false,
            existing_street: false,
            existing_city: false,
            existing_user_id: false,
            existing_owner_label: false,
            existing_team_label: false,
            existing_census_active: false,
            validation_state: "pending",
            validation_message: false,
        });
        if (this.timer) {
            clearTimeout(this.timer);
        }
        if (query.trim().length < 2) {
            this.state.results = [];
            this.state.loading = false;
            return;
        }
        this.timer = setTimeout(() => this.search(query), 260);
    }

    onFocus() {
        if (this.state.results.length || this.state.query.trim().length >= 2) {
            this.state.open = true;
        }
    }

    async search(query) {
        const serial = ++this.requestSerial;
        this.state.loading = true;
        try {
            const results = await this.orm.call(
                "conedera.census.customer.lookup.wizard",
                "search_global_candidates",
                [],
                { term: query, limit: 12 }
            );
            if (serial !== this.requestSerial) {
                return;
            }
            this.state.results = results || [];
            this.state.searched = true;
            this.state.open = true;
        } finally {
            if (serial === this.requestSerial) {
                this.state.loading = false;
            }
        }
    }

    async selectCandidate(candidate) {
        const status = candidate.can_request || (!candidate.can_open && !candidate.can_use) ? "restricted" : "found";
        const label = candidate.vat
            ? `${candidate.vat} · ${candidate.name}`
            : candidate.name;
        this.state.query = label;
        this.state.open = false;
        // Keep the actual typed search term in the transient record. The UI can show
        // a friendly selected label, while the server later revalidates that the chosen
        // partner really belonged to the current global search results.
        await this.props.record.update({
            selected_partner_ref_id: candidate.id,
            selected_candidate_status: candidate.status,
            selected_can_open: candidate.can_open,
            selected_can_use: candidate.can_use,
            selected_can_request_reassignment: candidate.can_request,
            selected_is_census: candidate.census_active,
            existing_partner_id: candidate.can_open || candidate.can_use ? [candidate.id, candidate.name] : false,
            existing_name: candidate.name || false,
            existing_vat: candidate.vat || false,
            existing_commercial_name: candidate.commercial_name || false,
            existing_phone: candidate.phone || false,
            existing_mobile: candidate.mobile || false,
            existing_email: candidate.email || false,
            existing_street: candidate.street || false,
            existing_city: candidate.city || false,
            existing_user_id: candidate.owner_id ? [candidate.owner_id, candidate.owner_label] : false,
            existing_owner_label: candidate.owner_label || false,
            existing_team_label: candidate.team_label || false,
            existing_census_active: candidate.census_active,
            validation_state: status,
            validation_message: candidate.status_label,
        });
    }

    clearSelection() {
        this.state.query = "";
        this.state.results = [];
        this.state.open = false;
        return this.props.record.update({
            [this.props.name]: false,
            selected_partner_ref_id: false,
            selected_candidate_status: false,
            selected_can_open: false,
            selected_can_use: false,
            selected_can_request_reassignment: false,
            selected_is_census: false,
            existing_partner_id: false,
            existing_name: false,
            existing_vat: false,
            existing_commercial_name: false,
            existing_phone: false,
            existing_mobile: false,
            existing_email: false,
            existing_street: false,
            existing_city: false,
            existing_user_id: false,
            existing_owner_label: false,
            existing_team_label: false,
            existing_census_active: false,
            validation_state: "pending",
            validation_message: false,
        });
    }
}

export const censusCustomerLookupField = {
    component: CensusCustomerLookupField,
    supportedTypes: ["char"],
};

registry.category("fields").add("census_customer_lookup", censusCustomerLookupField);
