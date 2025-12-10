/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";
import DynamicSnippetCarousel from "@website/snippets/s_dynamic_snippet_carousel/000";
import { rpc } from "@web/core/network/rpc";

const DynamicSnippetProducts = DynamicSnippetCarousel.extend({
    selector: '.s_dynamic_snippet_products',

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
        const brandDomain = this._getBrandSearchDomain();
        const finalDomain = searchDomain.concat(brandDomain);

        // 🔹 Depuración: ver el dominio final
        console.log("Dominio final:", finalDomain);

        // 🔹 Depuración: probar qué productos devuelve ese dominio
        rpc("/web/dataset/call_kw/product.product/search_read", {
            model: "product.product",
            method: "search_read",
            args: [finalDomain, ["id", "name", "dr_brand_value_id"]],
            kwargs: { limit: 5 },
        }).then(result => {
            console.log("Productos filtrados por marca:", result);
        });

        searchDomain.push(...brandDomain);
        return searchDomain;
    },
});

publicWidget.registry.dynamic_snippet_products = DynamicSnippetProducts;

export default DynamicSnippetProducts;

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
