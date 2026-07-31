/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component } from "@odoo/owl";

class VariableDragWidget extends Component {
    setup() {
        this.variables = this.props.record.data.variable_ids.records;
    }

    onDragStart(ev, variable) {
        // Al arrastrar, pasamos la expresión interna
        ev.dataTransfer.setData("text/plain", variable.data.expression);
    }
}

VariableDragWidget.template = "hr_ec_document.VariableDragWidget";

registry.category("fields").add("variable_drag", VariableDragWidget);
