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
                const records = await this.orm.searchRead(
                    "hr.ec.document.variable",
                    [
                        ["id", "in", ids]
                    ],
                    [
                        "name",
                        "expression"
                    ]
                );

                this.variables = records;
            }

        });

    }



    onDragStart(ev, variable) {

        ev.dataTransfer.setData(
            "text/plain",
            variable.expression
        );

    }

}

VariableDragWidget.template = "hr_recruitment_ec_contract.VariableDragWidget";
registry.category("fields").add(
    "variable_drag",
    VariableDragWidget
);