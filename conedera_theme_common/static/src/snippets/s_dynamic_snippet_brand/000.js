/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";

const DynamicSnippetProductsBrand = publicWidget.registry.dynamic_snippet_products.extend({

    /**
     * Filtro por marca
     *
     * @private
     */
    _getBrandSearchDomain() {
        const searchDomain = [];
        let productBrandId = this.$el.get(0).dataset.productBrandId;
        if (productBrandId && productBrandId !== 'all') {
            // Como el snippet trabaja sobre product.product, usamos dr_brand_value_id
            searchDomain.push(['dr_brand_value_id', '=', parseInt(productBrandId)]);
        }
        return searchDomain;
    },

    /**
     * @override
     */
    _getSearchDomain: function () {
        const searchDomain = this._super.apply(this, arguments);
        const brandDomain = this._getBrandSearchDomain();
        console.log("Dominio final con marca:", searchDomain.concat(brandDomain)); // 🔹 depuración
        searchDomain.push(...brandDomain);
        return searchDomain;
    },
});

publicWidget.registry.dynamic_snippet_products = DynamicSnippetProductsBrand;

export default DynamicSnippetProductsBrand;

// /** @odoo-module **/

// import publicWidget from "@web/legacy/js/public/public_widget";
// import { rpc } from "@web/core/network/rpc";
// import DynamicSnippetCarousel from "@website/snippets/s_dynamic_snippet_carousel/000";
// import wSaleUtils from "@website_sale/js/website_sale_utils";
// import { WebsiteSale } from "../../js/website_sale";

// const DynamicSnippetProducts = DynamicSnippetCarousel.extend({
//     selector: '.s_dynamic_snippet_products',

//     //--------------------------------------------------------------------------
//     // Private
//     //--------------------------------------------------------------------------

//     /**
//      * 🔹 Gets the brand search domain
//      *
//      * @private
//      */
//     _getBrandSearchDomain() {
//         const searchDomain = [];
//         let productBrandId = this.$el.get(0).dataset.productBrandId;
//         if (productBrandId && productBrandId !== 'all') {
//             searchDomain.push(['dr_brand_value_id', '=', parseInt(productBrandId)]);
//         }
//         return searchDomain;
//     },

//     /**
//      * @override
//      * @private
//      */
//     _getSearchDomain: function () {
//         const searchDomain = this._super.apply(this, arguments);
//         searchDomain.push(...this._getBrandSearchDomain());
//         return searchDomain;
//     },
// });

// publicWidget.registry.dynamic_snippet_products = DynamicSnippetProducts;

// export default DynamicSnippetProducts;
