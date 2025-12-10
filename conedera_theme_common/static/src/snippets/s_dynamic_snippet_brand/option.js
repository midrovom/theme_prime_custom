/** @odoo-module **/

import options from "@web_editor/js/editor/snippets.options";

const dynamicSnippetProductsOptionsBrand = options.registry.dynamic_snippet_products.extend({

    init: function () {
        this._super.apply(this, arguments);
        this.productBrands = {};
        this.orm = this.bindService("orm");
        console.log("Init ejecutado: productBrands inicializado y orm vinculado");
    },

    _fetchProductBrands: function () {
        return this.orm.searchRead(
            "product.attribute.value",
            [["attribute_id.dr_is_brand", "=", true]],
            ["id", "name", "display_name", "dr_image"]
        );
    },

    _renderProductBrandSelector: async function (uiFragment) {
        const productBrands = await this._fetchProductBrands();
        for (let brand of productBrands) {
            this.productBrands[brand.id] = brand;
        }
        const productBrandsSelectorEl = uiFragment.querySelector('[data-name="product_brand_opt"]');
        return this._renderSelectUserValueWidgetButtons(productBrandsSelectorEl, this.productBrands);
    },

    _renderCustomXML: async function (uiFragment) {
        await this._super.apply(this, arguments);   
        await this._renderProductBrandSelector(uiFragment); 
    },

    _setOptionsDefaultValues: function () {
        this._super.apply(this, arguments);         
        this._setOptionValue('productBrandId', 'all');
    },

    _setOptionValue: function (optionName, value) {
        this._super.apply(this, arguments);
        if (optionName === 'productBrandId') {
            this.$target[0].dataset.productBrandId = value;
            this.contextualFilterDomain = (this.contextualFilterDomain || []).filter(
                (c) => !(Array.isArray(c) && c[0] === 'dr_brand_value_id')
            );
            if (value && value !== 'all') {
                this.contextualFilterDomain.push(['dr_brand_value_id', '=', parseInt(value)]);
            }
            this.trigger_up('widgets_start_request', { $target: this.$target });
        }
    },
});

options.registry.dynamic_snippet_products = dynamicSnippetProductsOptionsBrand;

export default dynamicSnippetProductsOptionsBrand;


// /** @odoo-module **/

// import options from "@web_editor/js/editor/snippets.options";

// const dynamicSnippetProductsOptionsBrand = options.registry.dynamic_snippet_products.extend({

//     init: function () {
//         this._super.apply(this, arguments);
//         this.productBrands = {};
//         this.orm = this.bindService("orm");
//     },

//     _fetchProductBrands: function () {
//         return this.orm.searchRead(
//             "product.attribute.value",
//             [["attribute_id.dr_is_brand", "=", true]],
//             ["id", "name", "display_name", "dr_image"]
//         );
//     },

//     _renderProductBrandSelector: async function (uiFragment) {
//         const productBrands = await this._fetchProductBrands();
//         for (let brand of productBrands) {
//             this.productBrands[brand.id] = brand;
//         }
//         const productBrandsSelectorEl = uiFragment.querySelector('[data-name="product_brand_opt"]');
//         return this._renderSelectUserValueWidgetButtons(productBrandsSelectorEl, this.productBrands);
//     },

//     _renderCustomXML: async function (uiFragment) {
//         await this._super.apply(this, arguments);   
//         await this._renderProductBrandSelector(uiFragment); 
//     },

//     _setOptionsDefaultValues: function () {
//         this._super.apply(this, arguments);         
//         this._setOptionValue('productBrandId', 'all');
//     },

//     _setOptionValue: function (optionName, value) {
//         this._super.apply(this, arguments);
//         if (optionName === 'productBrandId') {
//             this.$target[0].dataset.productBrandId = value;
//             this.contextualFilterDomain = (this.contextualFilterDomain || []).filter(
//                 (c) => !(Array.isArray(c) && c[0] === 'dr_brand_value_id')
//             );
//             if (value && value !== 'all') {
//                 this.contextualFilterDomain.push(['dr_brand_value_id', '=', parseInt(value)]);
//             }
//         }
//     },
// });

// options.registry.dynamic_snippet_products = dynamicSnippetProductsOptionsBrand;

// export default dynamicSnippetProductsOptionsBrand;
