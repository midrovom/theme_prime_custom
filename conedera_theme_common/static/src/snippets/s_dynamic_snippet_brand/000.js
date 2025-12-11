/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";
import DynamicSnippetProducts from "@website_sale/snippets/s_dynamic_snippet_products/000";

const DynamicSnippetProductsBrand = DynamicSnippetProducts.extend({

    _getSearchDomain() {
        const domain = this._super(...arguments);
        const brandDomain = this._getBrandSearchDomain();
        domain.push(...brandDomain);
        return domain;
    },

    _getBrandSearchDomain() {
        let brandId = this.$el.get(0).dataset.productBrandId;
        if (!brandId || brandId === "all") {
            return [];
        }
        return [["attribute_line_ids.value_ids", "in", [parseInt(brandId)]]];
    },
});

publicWidget.registry.dynamic_snippet_products = DynamicSnippetProductsBrand;

export default DynamicSnippetProductsBrand;



// /** @odoo-module **/

// import publicWidget from "@web/legacy/js/public/public_widget";
// import DynamicSnippetProducts from "@website_sale/snippets/s_dynamic_snippet_products/000";

// const DynamicSnippetProductsBrand = DynamicSnippetProducts.extend({

//     _getSearchDomain() {
//         const domain = this._super(...arguments);
//         const brandDomain = this._getBrandSearchDomain();
//         domain.push(...brandDomain);
//         return domain;
//     },

//     _getBrandSearchDomain() {
//         let brandId = this.$el.get(0).dataset.productBrandId;
//         if (!brandId || brandId === "all") {
//             return [];
//         }
//         return [["attribute_line_ids.value_ids", "in", [parseInt(brandId)]]];
//     },


//     _getRpcParameters() {
//         const params = this._super(...arguments);
//         params.product_brand_img = this.$el.get(0).dataset.productBrandImg || "";
//         console.log("[widget] Imagen enviada al RPC:", params.product_brand_img);
//         return params;
//     },

// });

// publicWidget.registry.dynamic_snippet_products = DynamicSnippetProductsBrand;

// export default DynamicSnippetProductsBrand;



// /** @odoo-module **/

// import publicWidget from "@web/legacy/js/public/public_widget";
// import DynamicSnippetProducts from "@website_sale/snippets/s_dynamic_snippet_products/000";

// const DynamicSnippetProductsBrand = DynamicSnippetProducts.extend({

//     _getSearchDomain() {
//         const domain = this._super(...arguments);
//         const brandDomain = this._getBrandSearchDomain();
//         domain.push(...brandDomain);
//         return domain;
//     },

//     _getBrandSearchDomain() {
//         let brandId = this.$el.get(0).dataset.productBrandId;
//         if (!brandId || brandId === "all") {
//             return [];
//         }
//         return [["attribute_line_ids.value_ids", "in", [parseInt(brandId)]]];
//     },
// });

// publicWidget.registry.dynamic_snippet_products = DynamicSnippetProductsBrand;

// export default DynamicSnippetProductsBrand;

