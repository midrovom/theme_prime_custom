/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";
import DynamicSnippetProducts from "@website_sale/snippets/s_dynamic_snippet_products/000";
import { utils as uiUtils } from "@web/core/ui/ui_service";

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

    /**
     * Sobrescribimos el método que define el número de productos a mostrar.
     * Solo en versión web (desktop) limitamos a 2.
     */
    _getLimit() {
        if (uiUtils.isSmall()) {
            return this._super(...arguments);
        }
        return 2;
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
// });

// publicWidget.registry.dynamic_snippet_products = DynamicSnippetProductsBrand;

// export default DynamicSnippetProductsBrand;
