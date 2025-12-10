/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";
import DynamicSnippetProducts from "@website/snippets/s_dynamic_snippet_carousel/000";

const DynamicSnippetProductsBrand = DynamicSnippetProducts.extend({

    _getBrandSearchDomain() {
        const searchDomain = [];
        let productBrandId = this.$el.get(0).dataset.productBrandId;
        if (productBrandId && productBrandId !== 'all') {
            searchDomain.push(['dr_brand_value_id', '=', parseInt(productBrandId)]);
        }
        return searchDomain;
    },

    _getSearchDomain: function () {
        const searchDomain = this._super.apply(this, arguments);
        searchDomain.push(...this._getBrandSearchDomain());  
        return searchDomain;
    },
});

publicWidget.registry.dynamic_snippet_products = DynamicSnippetProductsBrand;

export default DynamicSnippetProductsBrand;
