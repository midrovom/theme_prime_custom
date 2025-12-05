import options from "@web_editor/js/editor/snippets.options";
import s_dynamic_snippet_carousel_options from "@website/snippets/s_dynamic_snippet_carousel/options";

const dynamicSnippetBrandOptions = s_dynamic_snippet_carousel_options.extend({
    /**
     * @override
     */

    // Override que define el filtro del modelo específico para marcas
    init() {
        this._super.apply(this, arguments);
        this.modelNameFilter = 'product.attribute.value';  
    },
});

// Registrar en el editor como nuevo snippet de marcas
options.registry.dynamic_snippet_brands = dynamicSnippetBrandOptions;

export default dynamicSnippetBrandOptions;
