/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component } from "@odoo/owl";

class VariableDragWidget extends Component {
    setup() {
        const records = this.props.record.data.variable_ids?.records || [];
        this.variables = records.map(r => ({
            name: r.data?.name,
            expression: r.data?.expression,
        }));
    }

    onDragStart(ev, variable) {
        ev.dataTransfer.setData("text/plain", variable.expression);
    }

}

VariableDragWidget.template = "hr_ec_document.VariableDragWidget";

registry.category("fields").add("variable_drag", VariableDragWidget);
