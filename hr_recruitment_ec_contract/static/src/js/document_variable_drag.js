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


    insertVariable(variable) {

        const text = "{{" + variable.key + "}}";

        const editor = document.querySelector(
            ".odoo-editor-editable"
        );

        if (!editor) {
            console.warn("Editor HTML no encontrado");
            return;
        }


        editor.focus();


        const selection = window.getSelection();

        if (!selection.rangeCount) {
            return;
        }


        const range = selection.getRangeAt(0);

        range.deleteContents();


        const node = document.createTextNode(text);

        range.insertNode(node);


        range.setStartAfter(node);
        range.setEndAfter(node);


        selection.removeAllRanges();
        selection.addRange(range);


        editor.dispatchEvent(
            new InputEvent(
                "input",
                {
                    bubbles:true,
                    inputType:"insertText",
                    data:text
                }
            )
        );

    }

}


registry.category("fields").add(
    "variable_drag",
    {
        component: VariableDragWidget,
    }
);