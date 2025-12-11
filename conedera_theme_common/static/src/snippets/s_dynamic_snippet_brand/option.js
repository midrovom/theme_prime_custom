/** @odoo-module **/

import options from "@web_editor/js/editor/snippets.options";

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

// console.log("%c[dynamic_snippet_products OPTIONS] Archivo cargado", "color: green; font-weight: bold;");

// options.registry.dynamic_snippet_products.include({

//     init: function () {
//         this._super(...arguments);
//         this.productBrands = {};
//         console.log("%c[dynamic_snippet_products] init()", "color: blue");
//     },

//     // -------------------------------------
//     // FETCH MARCAS
//     // -------------------------------------
//     _fetchProductBrands: function () {
//         console.log("%c[_fetchProductBrands] Ejecutado", "color: purple");

//         return this.orm.searchRead(
//             "product.attribute.value",
//             [["attribute_id.dr_is_brand", "=", true]],
//             ["id", "name", "attribute_id"]
//         ).then(result => {
//             console.log("[_fetchProductBrands] Resultado:", result);
//             return result;
//         });
//     },

//     // -------------------------------------
//     // RENDER OPTIONS XML
//     // -------------------------------------
//     async _renderCustomXML(uiFragment) {
//         console.log("%c[_renderCustomXML] Ejecutado", "color: orange");
//         await this._super(...arguments);
//         await this._renderProductBrandSelector(uiFragment);
//     },

//     async _renderProductBrandSelector(uiFragment) {
//         console.log("%c[_renderProductBrandSelector] Ejecutado", "color: #ff00ff");

//         const productBrands = await this._fetchProductBrands();

//         for (let entry of productBrands) {
//             this.productBrands[entry.id] = entry;
//         }

//         console.log("[_renderProductBrandSelector] Marcas procesadas:", this.productBrands);

//         const selectorEl = uiFragment.querySelector('[data-name="product_brand_opt"]');
//         console.log("[_renderProductBrandSelector] Selector encontrado:", selectorEl);

//         return this._renderSelectUserValueWidgetButtons(selectorEl, this.productBrands);
//     },

//     // -------------------------------------
//     // VALORES POR DEFECTO
//     // -------------------------------------
//     _setOptionsDefaultValues: function () {
//         console.log("%c[_setOptionsDefaultValues] Ejecutado", "color: brown");

//         this._setOptionValue("productBrandId", "all");

//         this._super(...arguments);

//         console.log("[_setOptionsDefaultValues] productBrandId = all");
//     },
// });


