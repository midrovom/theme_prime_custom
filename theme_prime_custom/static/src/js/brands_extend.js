/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";

publicWidget.registry.s_d_brand_snippet.include({

    _getOptions: function () {
        const result = this._super.apply(this, arguments);

        result.limit = 30;

        return result;
    },

});