/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";
import DynamicSnippetCarousel from "@website/snippets/s_dynamic_snippet_carousel/000";

const DynamicSnippetBrand = DynamicSnippetCarousel.extend({
    selector: ".s_dynamic_snippet_brand",

    /**
     * Agrega el filtro por marca
     */
    _getBrandDomain() {
        const brand = this.el.dataset.productBrandId || "all";
        if (brand === "all") {
            return [];
        }
        return [["dr_brand_value_id", "=", parseInt(brand)]];
    },

    /**
     * @override
     */
    _getSearchDomain() {
        const domain = this._super(...arguments);
        domain.push(...this._getBrandDomain());
        return domain;
    },

    /**
     * @override
     * Url de clic “ver más”
     */
    _getMainPageUrl() {
        return "/shop";
    },
});

publicWidget.registry.dynamic_snippet_brand = DynamicSnippetBrand;

export default DynamicSnippetBrand;


// /** @odoo-module **/

// import publicWidget from "@web/legacy/js/public/public_widget";
// import DynamicSnippetProducts from "@website/snippets/s_dynamic_snippet_products/000";

// const DynamicSnippetProductsBrand = DynamicSnippetProducts.extend({

//     /**
//      * Gets the brand search domain
//      *
//      * @private
//      */
//     _getBrandSearchDomain() {
//         const searchDomain = [];
//         let productBrandId = this.$el.get(0).dataset.productBrandId;
//         if (productBrandId && productBrandId !== 'all') {
//             // 🔹 Ahora filtramos por el campo dr_brand_value_id
//             searchDomain.push(['dr_brand_value_id', '=', parseInt(productBrandId)]);
//         }
//         return searchDomain;
//     },

//     /**
//      * Override search domain to include brand
//      *
//      * @override
//      * @private
//      */
//     _getSearchDomain: function () {
//         const searchDomain = this._super.apply(this, arguments);
//         searchDomain.push(...this._getBrandSearchDomain());
//         return searchDomain;
//     },
// });

// publicWidget.registry.dynamic_snippet_products_brand = DynamicSnippetProductsBrand;

// export default DynamicSnippetProductsBrand;

