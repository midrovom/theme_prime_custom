/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

export class VariableDragWidget extends Component {

    static template = "hr_recruitment_ec_contract.VariableDragWidget";

    static props = {
        ...standardFieldProps,
    };

    setup() {

        this.orm = useService("orm");
        this.variables = [];

        onWillStart(async () => {

            const ids = this.props.record.data.variable_ids?.resIds || [];

            if (!ids.length) {
                return;
            }

            this.variables = await this.orm.searchRead(
                "hr.ec.document.variable",
                [["id", "in", ids]],
                ["name", "key", "expression"]
            );

        });
    }

    insertVariable(variable) {

        const value = `{{${variable.key}}}`;

        window.dispatchEvent(
            new CustomEvent("ec_insert_variable", {
                detail: value,
            })
        );
    }
}

registry.category("fields").add("variable_drag", {
    component: VariableDragWidget,
});