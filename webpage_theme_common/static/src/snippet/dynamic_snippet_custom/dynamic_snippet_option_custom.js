/** @odoo-module **/

import options from "@web_editor/js/editor/snippets.options";
import publicWidget from "@web/legacy/js/public/public_widget";
import DynamicSnippetProducts from "@website_sale/js/s_dynamic_snippet_products"; // ojo: sin /000
import { utils as uiUtils } from "@web/core/ui/ui_service";

// --- OPCIONES DEL EDITOR ---
options.registry.dynamic_snippet_products.include({
    init() {
        this._super(...arguments);
        this.productBrands = {};
    },

    async _fetchProductBrands() {
        return this.orm.searchRead(
            "product.attribute.value",
            [["attribute_id.dr_is_brand", "=", true]],
            ["id", "name", "attribute_id"]
        );
    },

    async _renderCustomXML(uiFragment) {
        await this._super(...arguments);
        await this._renderProductBrandSelector(uiFragment);
    },

    async _renderProductBrandSelector(uiFragment) {
        const productBrands = await this._fetchProductBrands();
        for (let entry of productBrands) {
            this.productBrands[entry.id] = entry;
        }
        const selectorEl = uiFragment.querySelector('[data-name="product_brand_opt"]');
        return this._renderSelectUserValueWidgetButtons(selectorEl, this.productBrands);
    },

    _setOptionsDefaultValues() {
        this._setOptionValue("productBrandId", "all");
        this._super(...arguments);
    },
});

// --- WIDGET FRONTEND + BUILDER ---
const DynamicSnippetProductsUnified = DynamicSnippetProducts.extend({
    _getQWebRenderOptions() {
        const options = this._super(...arguments);
        const tplKey = this.$el.data("template-key");

        if (this.editableMode) {
            // reglas especiales para builder
            if (tplKey && tplKey.includes("dynamic_filter_template_product_product_style_2")) {
                options.chunkSize = 1;
            }
        } else if (uiUtils.isSmall()) {
            // móvil
            options.chunkSize = tplKey?.includes("style_1") ? 2 : 1;
        } else {
            // escritorio
            if (tplKey?.includes("style_2") || tplKey?.includes("style_1")) {
                options.chunkSize = 4;
            } else {
                options.chunkSize = 6;
            }
        }
        return options;
    },

    _getSearchDomain() {
        const domain = this._super(...arguments);
        const brandDomain = this._getBrandSearchDomain();
        domain.push(...brandDomain);
        return domain;
    },

    _getBrandSearchDomain() {
        const brandId = this.$el.get(0).dataset.productBrandId;
        if (!brandId || brandId === "all") {
            return [];
        }
        return [["attribute_line_ids.value_ids", "in", [parseInt(brandId)]]];
    },
});

publicWidget.registry.dynamic_snippet_products = DynamicSnippetProductsUnified;
export default DynamicSnippetProductsUnified;


// /** @odoo-module **/
// import publicWidget from "@web/legacy/js/public/public_widget";
// import DynamicSnippetProducts from "@website_sale/snippets/s_dynamic_snippet_products/000";

// const DynamicSnippetProductsWysiwyg = DynamicSnippetProducts.extend({
//     _getQWebRenderOptions() {
//         const options = this._super(...arguments);
//         const tplKey = this.$el.data("template-key");

//         // 🔑 Lógica especial para el builder
//         if (this.editableMode && tplKey && tplKey.includes("dynamic_filter_template_product_product_style_2")) {
//             options.chunkSize = 1; // siempre 1 producto en builder
//         }

//         return options;
//     },
// });

// publicWidget.registry.dynamic_snippet_products = DynamicSnippetProductsWysiwyg;
// export default DynamicSnippetProductsWysiwyg;