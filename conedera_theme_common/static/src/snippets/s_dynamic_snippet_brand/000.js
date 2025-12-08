/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";
import DynamicSnippetProducts from "@website/snippets/s_dynamic_snippet_products/000";

const DynamicSnippetProductsBrand = DynamicSnippetProducts.extend({

    /**
     * Gets the brand search domain
     *
     * @private
     */
    _getBrandSearchDomain() {
        const searchDomain = [];
        let productBrandId = this.$el.get(0).dataset.productBrandId;
        if (productBrandId && productBrandId !== 'all') {
            if (productBrandId === 'current') {
                // lógica para detectar la marca actual si estás en página de producto
                const productBrandField = $("#product_details").find(".product_brand_id");
                if (productBrandField && productBrandField.length) {
                    productBrandId = parseInt(productBrandField[0].value);
                }
            }
            if (productBrandId) {
                searchDomain.push(['product_brand_id', '=', parseInt(productBrandId)]);
            }
        }
        return searchDomain;
    },

    /**
     * Override search domain to include brand
     *
     * @override
     * @private
     */
    _getSearchDomain: function () {
        const searchDomain = this._super.apply(this, arguments);
        searchDomain.push(...this._getBrandSearchDomain());
        return searchDomain;
    },
});

publicWidget.registry.dynamic_snippet_products_brand = DynamicSnippetProductsBrand;

export default DynamicSnippetProductsBrand;
