/** @odoo-module **/

import options from '@web_editor/js/editor/snippets.options';
import dynamicSnippetOptions from '@website/snippets/s_dynamic_snippet/options';

const dynamicSnippetCategoryOptions = dynamicSnippetOptions.extend({
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
