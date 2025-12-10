/** @odoo-module **/

import options from "@web_editor/js/editor/snippets.options";
import s_dynamic_snippet_carousel_options from "@website/snippets/s_dynamic_snippet_carousel/options";
import wUtils from "@website/js/utils";

const dynamicSnippetProductsOptions = s_dynamic_snippet_carousel_options.extend({

    init: function () {
        this._super.apply(this, arguments);
        this.productBrands = {};   // 🔹 Diccionario para marcas
        this.orm = this.bindService("orm");
    },

    //--------------------------------------------------------------------------
    // 🔹 Marcas
    //--------------------------------------------------------------------------

    /**
     * Trae las marcas desde product.attribute.value
     * Solo aquellas cuyo atributo padre tiene dr_is_brand = true
     */
    _fetchProductBrands: function () {
        return this.orm.searchRead(
            "product.attribute.value",
            [["attribute_id.dr_is_brand", "=", true]],
            ["id", "name", "display_name", "dr_image"]
        );
    },

    /**
     * Renderiza el selector de marcas en el editor
     */
    _renderProductBrandSelector: async function (uiFragment) {
        const productBrands = await this._fetchProductBrands();
        for (let brand of productBrands) {
            this.productBrands[brand.id] = brand;
        }
        const productBrandsSelectorEl = uiFragment.querySelector('[data-name="product_brand_opt"]');
        return this._renderSelectUserValueWidgetButtons(productBrandsSelectorEl, this.productBrands);
    },

    //--------------------------------------------------------------------------
    // Renderizado general
    //--------------------------------------------------------------------------

    _renderCustomXML: async function (uiFragment) {
        await this._super.apply(this, arguments);
        await this._renderProductBrandSelector(uiFragment);  
    },

    //--------------------------------------------------------------------------
    // Valores por defecto
    //--------------------------------------------------------------------------

    _setOptionsDefaultValues: function () {
        this._setOptionValue('productBrandId', 'all');   
        this._super.apply(this, arguments);
    },

    /**
     * Guardar selección en el DOM y actualizar dominio contextual
     */
    _setOptionValue: function (optionName, value) {
        this._super.apply(this, arguments);
        if (optionName === 'productBrandId') {
            this.$target[0].dataset.productBrandId = value;

            if (this.contextualFilterDomain) {
                this.contextualFilterDomain = this.contextualFilterDomain.filter(
                    (c) => !(Array.isArray(c) && c[0] === 'dr_brand_value_id')
                );
            } else {
                this.contextualFilterDomain = [];
            }

            if (value && value !== 'all') {
                this.contextualFilterDomain.push(['dr_brand_value_id', '=', parseInt(value)]);
            }
        }
    },
});

options.registry.dynamic_snippet_products = dynamicSnippetProductsOptions;

export default dynamicSnippetProductsOptions;

// /** @odoo-module **/

// import options from "@web_editor/js/editor/snippets.options";
// import s_dynamic_snippet_carousel_options from "@website/snippets/s_dynamic_snippet_carousel/options";
// import wUtils from "@website/js/utils";

// const dynamicSnippetProductsOptions = s_dynamic_snippet_carousel_options.extend({

//     init: function () {
//         this._super.apply(this, arguments);
//         this.productBrands = {};
//         this.orm = this.bindService("orm");
//     },

//     _fetchProductBrands: function () {
//         return this.orm.searchRead(
//             "product.product",
//             wUtils.websiteDomain(this),
//             ["dr_brand_value_id"]
//         );
//     },

//     async _renderCustomXML(uiFragment) {
//         await this._super.apply(this, arguments);
//         await this._renderProductBrandSelector(uiFragment);
//     },

//     async _renderProductBrandSelector(uiFragment) {
//         const products = await this._fetchProductBrands();
//         for (let product of products) {
//             if (product.dr_brand_value_id) {
//                 const [id, name] = product.dr_brand_value_id;
//                 if (!this.productBrands[id]) {
//                     this.productBrands[id] = { id, name };
//                 }
//             }
//         }
//         const productBrandsSelectorEl = uiFragment.querySelector('[data-name="product_brand_opt"]');
//         return this._renderSelectUserValueWidgetButtons(productBrandsSelectorEl, this.productBrands);
//     },

//     _setOptionsDefaultValues: function () {
//         this._setOptionValue('productBrandId', 'all');
//         this._super.apply(this, arguments);
//     },

//     _setOptionValue: function (optionName, value) {
//         this._super.apply(this, arguments);
//         if (optionName === 'productBrandId') {
//             // Guardar en el DOM
//             this.$target[0].dataset.productBrandId = value;

//             // Limpiar entradas previas de marca en el dominio contextual
//             if (this.contextualFilterDomain) {
//                 this.contextualFilterDomain = this.contextualFilterDomain.filter(
//                     (c) => !(Array.isArray(c) && c[0] === 'dr_brand_value_id')
//                 );
//             } else {
//                 this.contextualFilterDomain = [];
//             }

//             // Añadir nueva marca seleccionada
//             if (value && value !== 'all') {
//                 this.contextualFilterDomain.push(['dr_brand_value_id', '=', parseInt(value)]);
//             }
//         }
//     },
// });

// options.registry.dynamic_snippet_products = dynamicSnippetProductsOptions;

// export default dynamicSnippetProductsOptions;
