/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { HtmlField } from "@web/views/fields/html/html_field";

patch(HtmlField.prototype, {

    setup() {
        super.setup();

        this.onDropVariable = (ev) => {

            const text = ev.dataTransfer.getData("text/plain");

            if (!text) {
                return;
            }

            ev.preventDefault();

            const editor = this.el.querySelector(".odoo-editor-editable");

            if (editor) {
                editor.focus();

                document.execCommand(
                    "insertText",
                    false,
                    text
                );
            }
        };
    },


    mounted() {
        super.mounted();

        const editor = this.el.querySelector(".odoo-editor-editable");

        if (editor) {
            editor.addEventListener(
                "drop",
                this.onDropVariable
            );
        }
    },


    willUnmount() {

        const editor = this.el.querySelector(".odoo-editor-editable");

        if (editor) {
            editor.removeEventListener(
                "drop",
                this.onDropVariable
            );
        }

        super.willUnmount();
    }

});