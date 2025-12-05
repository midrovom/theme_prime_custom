/** @odoo-module **/

import options from "@web_editor/js/editor/snippets.options";
import s_dynamic_snippet_carousel_options from "@website/snippets/s_dynamic_snippet_carousel/options";

const DynamicSnippetBrandOptions = s_dynamic_snippet_carousel_options.extend({

    init() {
        this._super(...arguments);
        this.orm = this.bindService("orm");
        this.brands = {};
    },

    /**
     * Load brands into the dropdown selector
     */
    async _renderCustomXML(uiFragment) {
        await this._super(...arguments);
        await this._renderBrandSelector(uiFragment);
    },

    async _renderBrandSelector(uiFragment) {

        // Load all attribute values belonging to the attribute "Marca"
        const brandValues = await this.orm.searchRead(
            "product.attribute.value",
            [["attribute_id.name", "=", "Marca"]],
            ["id", "name"]
        );

        brandValues.forEach(value => {
            this.brands[value.id] = value.name;
        });

        const el = uiFragment.querySelector('[data-name="product_brand_opt"]');

        return this._renderSelectUserValueWidgetButtons(el, this.brands);
    },

    /**
     * Default value when snippet is added
     */
    _setOptionsDefaultValues() {
        this._setOptionValue("brandId", "all");
        this._super(...arguments);
    },

});

options.registry.dynamic_snippet_brand = DynamicSnippetBrandOptions;

export default DynamicSnippetBrandOptions;
