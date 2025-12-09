/** @odoo-module **/

import options from "@web_editor/js/editor/snippets.options";
import s_dynamic_snippet_carousel_options from "@website/snippets/s_dynamic_snippet_carousel/options";
import wUtils from "@website/js/utils";

const dynamicSnippetProductsOptions = s_dynamic_snippet_carousel_options.extend({

    init: function () {
        this._super.apply(this, arguments);
        this.productBrands = {};   
        this.orm = this.bindService("orm");
    },

    _fetchProductBrands: function () {
        return this.orm.searchRead(
            "product.product",
            wUtils.websiteDomain(this),
            ["dr_brand_value_id"]
        );
    },

    async _renderCustomXML(uiFragment) {
        await this._super.apply(this, arguments);
        await this._renderProductBrandSelector(uiFragment);  
    },

    async _renderProductBrandSelector(uiFragment) {
        const products = await this._fetchProductBrands();
        for (let product of products) {
            if (product.dr_brand_value_id) {
                const [id, name] = product.dr_brand_value_id;
                if (!this.productBrands[id]) {
                    this.productBrands[id] = { id, name };
                }
            }
        }
        const productBrandsSelectorEl = uiFragment.querySelector('[data-name="product_brand_opt"]');
        return this._renderSelectUserValueWidgetButtons(productBrandsSelectorEl, this.productBrands);
    },

    _setOptionsDefaultValues: function () {
        this._setOptionValue('productBrandId', 'all');   
        this._super.apply(this, arguments);
    },

    _setOptionValue: function (optionName, value) {
        this._super.apply(this, arguments);
        if (optionName === 'productBrandId') {
            this.$target[0].dataset.productBrandId = value;
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

//     //--------------------------------------------------------------------------
//     // Private
//     //--------------------------------------------------------------------------

//     /**
//      * Fetches product brands from product.product.
//      * @private
//      * @returns {Promise}
//      */
//     _fetchProductBrands: function () {
//         return this.orm.searchRead(
//             "product.product",
//             wUtils.websiteDomain(this),
//             ["dr_brand_value_id"]
//         );
//     },

//     /**
//      * @override
//      * @private
//      */
//     async _renderCustomXML(uiFragment) {
//         await this._super.apply(this, arguments);
//         await this._renderProductBrandSelector(uiFragment);  
//     },

//     /**
//      * Renders the product brands option selector content.
//      * @private
//      */
//     async _renderProductBrandSelector(uiFragment) {
//         const products = await this._fetchProductBrands();
//         for (let product of products) {
//             if (product.dr_brand_value_id) {
//                 const [id, name] = product.dr_brand_value_id;
//                 if (!this.productBrands[id]) {   // evitar duplicados
//                     this.productBrands[id] = { id, name };
//                 }
//             }
//         }
//         const productBrandsSelectorEl = uiFragment.querySelector('[data-name="product_brand_opt"]');
//         return this._renderSelectUserValueWidgetButtons(productBrandsSelectorEl, this.productBrands);
//     },

//     /**
//      * @override
//      * @private
//      */
//     _setOptionsDefaultValues: function () {
//         this._setOptionValue('productBrandId', 'all');   
//         this._super.apply(this, arguments);
//     },

//     /**
//      * NUEVO: Guardar el dataset cuando se selecciona una marca
//      */
//     _setOptionValue: function (optionName, value) {
//         this._super.apply(this, arguments);
//         if (optionName === 'productBrandId') {
//             this.$target[0].dataset.productBrandId = value;
//         }
//     },
// });

// options.registry.dynamic_snippet_products = dynamicSnippetProductsOptions;

// export default dynamicSnippetProductsOptions;

