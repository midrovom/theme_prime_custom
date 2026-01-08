/** @odoo-module **/

import options from "@web_editor/js/editor/snippets.options";
import { utils as uiUtils } from "@web/core/ui/ui_service";

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
            this.$el.data("chunk-size", 1); // siempre 1 producto en builder
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


// /** @odoo-module **/

// import options from "@web_editor/js/editor/snippets.options";

// options.registry.dynamic_snippet_products.include({

//     init: function () {
//         this._super(...arguments);
//         this.productBrands = {};
//     },

//     // Fetch marcas

//     _fetchProductBrands: function () {
//         return this.orm.searchRead(
//             "product.attribute.value",
//             [["attribute_id.dr_is_brand", "=", true]],
//             ["id", "name", "attribute_id"]
//         ).then(result => {
//             return result;
//         });
//     },

//     // RENDER OPTIONS XML

//     async _renderCustomXML(uiFragment) {
//         await this._super(...arguments);
//         await this._renderProductBrandSelector(uiFragment);
//     },

//     async _renderProductBrandSelector(uiFragment) {
//         const productBrands = await this._fetchProductBrands();

//         for (let entry of productBrands) {
//             this.productBrands[entry.id] = entry;
//         }

//         const selectorEl = uiFragment.querySelector('[data-name="product_brand_opt"]');
//         return this._renderSelectUserValueWidgetButtons(selectorEl, this.productBrands);
//     },

//     // Valores por defecto
//     _setOptionsDefaultValues: function () {
//         this._setOptionValue("productBrandId", "all");
//         this._super(...arguments);
//     },
// });
