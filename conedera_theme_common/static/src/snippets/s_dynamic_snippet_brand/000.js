/** @odoo-module **/

import options from "@web_editor/js/editor/snippets.options";

const DynamicSnippetProductsOptionsBrand = options.registry.dynamic_snippet_products.extend({

    init: function () {
        this._super.apply(this, arguments);
        this.productBrands = {};
        this.orm = this.bindService("orm");
    },

    _fetchProductBrands: function () {
        return this.orm.searchRead(
            "product.attribute.value",
            [["attribute_id.dr_is_brand", "=", true]],
            ["id", "name", "display_name"]
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

options.registry.dynamic_snippet_products = DynamicSnippetProductsOptionsBrand;

export default DynamicSnippetProductsOptionsBrand;

// /** @odoo-module **/

// import publicWidget from "@web/legacy/js/public/public_widget";
// import { rpc } from "@web/core/network/rpc";
// import DynamicSnippetCarousel from "@website/snippets/s_dynamic_snippet_carousel/000";
// import wSaleUtils from "@website_sale/js/website_sale_utils";
// import { WebsiteSale } from "../../js/website_sale";

// const DynamicSnippetProducts = DynamicSnippetCarousel.extend({
//     selector: '.s_dynamic_snippet_products',

//     //--------------------------------------------------------------------------
//     // Private
//     //--------------------------------------------------------------------------

//     /**
//      * 🔹 Gets the brand search domain
//      *
//      * @private
//      */
//     _getBrandSearchDomain() {
//         const searchDomain = [];
//         let productBrandId = this.$el.get(0).dataset.productBrandId;
//         if (productBrandId && productBrandId !== 'all') {
//             searchDomain.push(['dr_brand_value_id', '=', parseInt(productBrandId)]);
//         }
//         return searchDomain;
//     },

//     /**
//      * @override
//      * @private
//      */
//     _getSearchDomain: function () {
//         const searchDomain = this._super.apply(this, arguments);
//         searchDomain.push(...this._getBrandSearchDomain());
//         return searchDomain;
//     },
// });

// publicWidget.registry.dynamic_snippet_products = DynamicSnippetProducts;

// export default DynamicSnippetProducts;
