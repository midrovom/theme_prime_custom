/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";

publicWidget.registry.dynamic_snippet_products.include({
    _getSearchDomain: function () {
        const searchDomain = this._super.apply(this, arguments);
        const productBrandId = this.$el.get(0).dataset.productBrandId;

        if (productBrandId && productBrandId !== 'all') {
            searchDomain.push(['product_tmpl_id.attribute_line_ids.value_ids', 'in', [parseInt(productBrandId)]]);
        }

        return searchDomain;
    },
});

