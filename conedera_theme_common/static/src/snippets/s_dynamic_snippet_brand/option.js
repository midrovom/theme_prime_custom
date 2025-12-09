/** @odoo-module **/

import options from "@web_editor/js/editor/snippets.options";
import s_dynamic_snippet_carousel_options from "@website/snippets/s_dynamic_snippet_carousel/options";
import wUtils from "@website/js/utils";

const dynamicSnippetBrandsOptions = s_dynamic_snippet_carousel_options.extend({

    init: function () {
        this._super.apply(this, arguments);
        this.modelNameFilter = 'product.product';
        this.productBrands = {};
        this.orm = this.bindService("orm");
    },

    /**
     * Fetch brands from product.brand (or your custom model).
     * @private
     */
    _fetchProductBrands: function () {
        return this.orm.searchRead("product.brand", wUtils.websiteDomain(this), ["id", "name"]);
    },

    /**
     * Render custom XML with brand selector.
     * @override
     */
    _renderCustomXML: async function (uiFragment) {
        await this._super.apply(this, arguments);
        await this._renderProductBrandSelector(uiFragment);
    },

    /**
     * Render brand selector buttons.
     * @private
     */
    _renderProductBrandSelector: async function (uiFragment) {
        const productBrands = await this._fetchProductBrands();
        for (let index in productBrands) {
            this.productBrands[productBrands[index].id] = productBrands[index];
        }
        const productBrandsSelectorEl = uiFragment.querySelector('[data-name="product_brand_opt"]');
        return this._renderSelectUserValueWidgetButtons(productBrandsSelectorEl, this.productBrands);
    },
});

options.registry.dynamic_snippet_brand = dynamicSnippetBrandsOptions;

export default dynamicSnippetBrandsOptions;
