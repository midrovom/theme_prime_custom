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

// console.log("%c[DynamicSnippetProductsBrand] Archivo cargado", "color: green; font-weight: bold;");

// const DynamicSnippetProductsBrand = DynamicSnippetProducts.extend({

//     _getSearchDomain() {
//         console.log("%c[DynamicSnippetProductsBrand] _getSearchDomain ejecutado", "color: orange");

//         const domain = this._super(...arguments);

//         const brandDomain = this._getBrandSearchDomain();
//         console.log("[DynamicSnippetProductsBrand] Dominio marca:", brandDomain);

//         domain.push(...brandDomain);

//         console.log("%c[DynamicSnippetProductsBrand] Dominio final:", "color: yellow", domain);
//         return domain;
//     },

//     _getBrandSearchDomain() {
//         console.log("%c[DynamicSnippetProductsBrand] _getBrandSearchDomain()", "color: purple");

//         let brandId = this.$el.get(0).dataset.productBrandId;
//         console.log("[DynamicSnippetProductsBrand] brandId leido:", brandId);

//         if (!brandId || brandId === "all") {
//             return [];
//         }

//         return [["attribute_line_ids.value_ids", "in", [parseInt(brandId)]]];
//     },
// });

// publicWidget.registry.dynamic_snippet_products = DynamicSnippetProductsBrand;

// export default DynamicSnippetProductsBrand;
