/** @odoo-module **/

import options from "@web_editor/js/editor/snippets.options";
import dynamicSnippetProductsOptions from "@website/snippets/s_dynamic_snippet_carousel/options";  // 👈 Importas el original
import wUtils from "@website/js/utils";

const dynamicSnippetProductsOptionsBrand = dynamicSnippetProductsOptions.extend({

    init: function () {
        this._super.apply(this, arguments);
        this.productBrands = {};   
    },

    // -------------------------------
    // Fetch marcas
    // -------------------------------
    _fetchProductBrands: function () {
        return this.orm.searchRead("product.attribute.value", [["attribute_id.dr_is_brand", "=", true]], ["id", "name", "attribute_id"]);
    },
    // _fetchProductBrands: function () {
    //     return this.orm.searchRead("product.template.attribute.line", wUtils.websiteDomain(this), ["id", "name"]);
    // },

    // -------------------------------
    // Render marcas
    // -------------------------------
    async _renderCustomXML(uiFragment) {
        await this._super.apply(this, arguments);
        await this._renderProductBrandSelector(uiFragment);  
    },

    async _renderProductBrandSelector(uiFragment) {
        const productBrands = await this._fetchProductBrands();
        for (let index in productBrands) {
            this.productBrands[productBrands[index].id] = productBrands[index];
        }
        const productBrandsSelectorEl = uiFragment.querySelector('[data-name="product_brand_opt"]');
        return this._renderSelectUserValueWidgetButtons(productBrandsSelectorEl, this.productBrands);
    },

    _setOptionsDefaultValues: function () {
        this._super.apply(this, arguments);
        this._setOptionValue('productBrandId', 'all');   
    },
});

options.registry.dynamic_snippet_products = dynamicSnippetProductsOptionsBrand;

export default dynamicSnippetProductsOptionsBrand;
