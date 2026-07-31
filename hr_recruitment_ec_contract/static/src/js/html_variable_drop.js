/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { Wysiwyg } from "@web_editor/js/wysiwyg/wysiwyg";

patch(Wysiwyg.prototype, {

    async startEdition() {
        const res = await super.startEdition(...arguments);

        console.log("Wysiwyg:", this);
        console.log("OdooEditor:", this.odooEditor);
        console.log("Métodos:", Object.keys(this.odooEditor));

        return res;
    },

});