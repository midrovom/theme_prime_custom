/** @odoo-module **/

import options from "@web_editor/js/editor/snippets.options";
import s_dynamic_snippet_carousel_options from "@website/snippets/s_dynamic_snippet_carousel/options";

const DynamicSnippetBrandOptions = s_dynamic_snippet_carousel_options.extend({
    init() {
        this._super(...arguments);
        this.modelNameFilter = "product.template";
        this.orm = this.bindService("orm");
        this.productBrands = {};
    },

    async _fetchProductBrands() {
        const brandAttr = await this.orm.searchRead(
            "product.attribute",
            [["name", "=", "Marca"]],
            ["id"]
        );

        if (!brandAttr.length) {
            return [];
        }

        return this.orm.searchRead(
            "product.attribute.value",
            [["attribute_id", "=", brandAttr[0].id]],
            ["id", "name"]
        );
    },

    async _renderCustomXML(uiFragment) {
        await this._super(...arguments);
        await this._renderBrandSelector(uiFragment);
    },

    async _renderBrandSelector(uiFragment) {
        const brands = await this._fetchProductBrands();

        for (const b of brands) {
            this.productBrands[b.id] = b;
        }

        const brandSelectorEl = uiFragment.querySelector('[data-name="product_brand_opt"]');
        if (!brandSelectorEl) return;

        return this._renderSelectUserValueWidgetButtons(brandSelectorEl, this.productBrands);
    },

    _setOptionsDefaultValues() {
        this._setOptionValue("productBrandId", "all");
        this._super(...arguments);
    },
});

options.registry.dynamic_snippet_brand = DynamicSnippetBrandOptions;

export default DynamicSnippetBrandOptions;
