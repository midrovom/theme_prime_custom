/** @odoo-module **/

import options from "@web_editor/js/editor/snippets.options";
import s_dynamic_snippet_carousel_options from "@website/snippets/s_dynamic_snippet_carousel/options";

const dynamicSnippetCategoryOptions = s_dynamic_snippet_carousel_options.extend({
    /**
     * @override
     */
    init() {
        this._super.apply(this, arguments);
        this.modelNameFilter = 'product.public.category';
    },

    _setOptionsDefaultValues() {
        this._setOptionValue('numberOfRecords', 3);
        this._super.apply(this, arguments);
    },

});

options.registry.dynamic_snippet_categories = dynamicSnippetCategoryOptions;

export default dynamicSnippetCategoryOptions;
