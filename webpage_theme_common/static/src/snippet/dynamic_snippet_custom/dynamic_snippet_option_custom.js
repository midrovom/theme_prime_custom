/** @odoo-module **/

import options from "@web_editor/js/editor/snippets.options";
import publicWidget from "@web/legacy/js/public/public_widget";
import DynamicSnippetProducts from "@website_sale/snippets/s_dynamic_snippet_products/000";

options.registry.dynamic_snippet_products.include({

    init: function () {
        this._super(...arguments);
        this.productBrands = {};
    },

    // Fetch marcas
    _fetchProductBrands: function () {
        return this.orm.searchRead(
            "product.attribute.value",
            [["attribute_id.dr_is_brand", "=", true]],
            ["id", "name", "attribute_id"]
        ).then(result => {
            return result;
        });
    },

    // RENDER OPTIONS XML
    async _renderCustomXML(uiFragment) {
        await this._super(...arguments);
        await this._renderProductBrandSelector(uiFragment);

        // 🔑 Lógica especial SOLO para template style_2 en modo editable
        const tplKey = this.$el.data("template-key");
        if (this.editableMode && tplKey && tplKey.includes("dynamic_filter_template_product_product_style_2")) {
            this.$el.data("chunk-size", 1); // fuerza 1 producto en builder
        }
    },

    async _renderProductBrandSelector(uiFragment) {
        const productBrands = await this._fetchProductBrands();

        for (let entry of productBrands) {
            this.productBrands[entry.id] = entry;
        }

        const selectorEl = uiFragment.querySelector('[data-name="product_brand_opt"]');
        return this._renderSelectUserValueWidgetButtons(selectorEl, this.productBrands);
    },

    // Valores por defecto
    _setOptionsDefaultValues: function () {
        this._setOptionValue("productBrandId", "all");
        this._super(...arguments);
    },
});

// 🔑 Extensión del widget para aplicar chunkSize en builder
const DynamicSnippetProductsWysiwyg = DynamicSnippetProducts.extend({
    _getQWebRenderOptions() {
        const options = this._super(...arguments);
        const tplKey = this.$el.data("template-key");

        if (this.editableMode && tplKey && tplKey.includes("dynamic_filter_template_product_product_style_2")) {
            options.chunkSize = 1; // siempre 1 producto en builder
        }

        return options;
    },
});

publicWidget.registry.dynamic_snippet_products = DynamicSnippetProductsWysiwyg;
export default DynamicSnippetProductsWysiwyg;


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
