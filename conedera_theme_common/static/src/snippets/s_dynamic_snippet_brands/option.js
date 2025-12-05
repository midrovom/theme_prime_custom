import options from "@web_editor/js/editor/snippets.options";
import s_dynamic_snippet_carousel_options from "@website/snippets/s_dynamic_snippet_carousel/options";

const dynamicSnippetBrandOptions = s_dynamic_snippet_carousel_options.extend({

    init() {
        this._super.apply(this, arguments);

        this.modelNameFilter = 'product.attribute.value';  
    },
});

options.registry.dynamic_snippet_brand = dynamicSnippetBrandOptions;

export default dynamicSnippetBrandOptions;
