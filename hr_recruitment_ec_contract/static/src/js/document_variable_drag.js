/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

class VariableDragWidget extends Component {

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

        /*
            Lo que se insertará en el editor HTML
        */

        ev.dataTransfer.setData(
            "text/plain",
            "{{" + variable.key + "}}"
        );

        ev.dataTransfer.effectAllowed = "copy";

    }

}

VariableDragWidget.template =
    "hr_recruitment_ec_contract.VariableDragWidget";


registry.category("fields").add(
    "variable_drag",
    VariableDragWidget
);