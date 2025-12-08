/** @odoo-module **/

import { DynamicSnippetCarousel } from "@website/snippets/dynamic_snippet_carousel";
import { registry } from "@web/core/registry";

export class DynamicSnippetBrand extends DynamicSnippetCarousel {
    static selector = ".s_dynamic_snippet_brand";

    // ---------------------------
    // BRAND FILTER
    // ---------------------------
    getBrandDomain() {
        const brandId = this.props.product_brand_id || "all";
        if (brandId === "all") {
            return [];
        }
        return [["dr_brand_value_id", "=", parseInt(brandId)]];
    }

    getSearchDomain() {
        const domain = super.getSearchDomain();
        domain.push(...this.getBrandDomain());
        return domain;
    }

    getMainPageUrl() {
        return "/shop";
    }
}

registry.category("public_widgets").add("DynamicSnippetBrand", DynamicSnippetBrand);


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

