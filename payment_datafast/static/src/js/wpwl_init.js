/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";

publicWidget.registry.DatafastInit = publicWidget.Widget.extend({
    selector: '.o_payment_form',
    start: function () {
        if (typeof window.wpwlOptions?.onReady === "function") {
            window.wpwlOptions.onReady();
        }
    },
});
