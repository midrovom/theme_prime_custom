/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";
import { rpc } from "@web/core/network/rpc";
import DynamicSnippetCarousel from "@website/snippets/s_dynamic_snippet_carousel/000";
import wSaleUtils from "@website_sale/js/website_sale_utils";
import { WebsiteSale } from "../../js/website_sale";

const DynamicSnippetProducts = DynamicSnippetCarousel.extend({
    selector: '.s_dynamic_snippet_products',

    //--------------------------------------------------------------------------
    // Private
    //--------------------------------------------------------------------------

    /**
     * 🔹 Gets the brand search domain
     *
     * @private
     */
    _getBrandSearchDomain() {
        const searchDomain = [];
        let productBrandId = this.$el.get(0).dataset.productBrandId;
        if (productBrandId && productBrandId !== 'all') {
            searchDomain.push(['dr_brand_value_id', '=', parseInt(productBrandId)]);
        }
        return searchDomain;
    },

    /**
     * @override
     * @private
     */
    _getSearchDomain: function () {
        const searchDomain = this._super.apply(this, arguments);
        searchDomain.push(...this._getBrandSearchDomain());
        return searchDomain;
    },
});

publicWidget.registry.dynamic_snippet_products = DynamicSnippetProducts;

export default DynamicSnippetProducts;

// /** @odoo-module **/

// import publicWidget from "@web/legacy/js/public/public_widget";
// import DynamicSnippetProducts from "website.snippets.s_dynamic_snippet_products.000";

// const DynamicSnippetProductsBrand = DynamicSnippetProducts.extend({

//     _getSearchDomain: function () {
//         const searchDomain = this._super.apply(this, arguments);
//         const el = this.$el.get(0);
//         const productBrandId = el && el.dataset ? el.dataset.productBrandId : null;

//         console.log(">>> _getSearchDomain brandId:", productBrandId);

//         if (productBrandId && productBrandId !== 'all') {
//             searchDomain.push(['dr_brand_value_id', '=', parseInt(productBrandId)]);
//         }

//         console.log(">>> searchDomain final:", searchDomain);
//         return searchDomain;
//     },

//     _getSearchContext: function () {
//         const searchContext = this._super.apply(this, arguments);
//         const el = this.$el.get(0);
//         const productBrandId = el && el.dataset ? el.dataset.productBrandId : null;

//         console.log(">>> _getSearchContext brandId:", productBrandId);

//         if (productBrandId && productBrandId !== 'all') {
//             searchContext.product_brand_id = parseInt(productBrandId);
//         }
//         return searchContext;
//     },
// });

// publicWidget.registry.dynamic_snippet_products = DynamicSnippetProductsBrand;

// export default DynamicSnippetProductsBrand;

