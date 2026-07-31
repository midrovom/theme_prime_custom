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
            if (ids.length) {

                this.variables = await this.orm.searchRead(
                    "hr.ec.document.variable",
                    [
                        ["id", "in", ids]
                    ],
                    [
                        "name",
                        "key",
                        "expression"
                    ]
                );

            }

        });

    }

    onDragStart(ev, variable) {

        const text = "{{" + variable.key + "}}";
        console.log("Dragging:", text);
        
        ev.dataTransfer.effectAllowed = "copy";

        ev.dataTransfer.setData(
            "text/plain",
            "{{" + variable.key + "}}"
        );

    }

}


registry.category("fields").add(
    "variable_drag",
    {
        component: VariableDragWidget,
    }
);