/** @odoo-module **/

import options from "@web_editor/js/editor/snippets.options";
import s_dynamic_snippet_carousel_options from "@website/snippets/s_dynamic_snippet_carousel/options";

import wUtils from "@website/js/utils";

const DynamicSnippetCategoriesOptions = s_dynamic_snippet_carousel_options.extend({

    /**
     * Inicializa opciones del snippet
     */
    init() {
        this._super(...arguments);
        this.modelNameFilter = "product.public.category"; // 🚀 Aquí definimos el modelo
        this.categoryItems = {};
        this.orm = this.bindService("orm");
    },

    // -------------------------------------------------------------------------
    // Private
    // -------------------------------------------------------------------------

    /**
     * Cargar categorías públicas para selector
     */
    _fetchCategories() {
        return this.orm.searchRead(
            "product.public.category",
            wUtils.websiteDomain(this),
            ["id", "name"]
        );
    },

    /**
     * Renderizar select de categoría padre
     */
    async _renderCustomXML(uiFragment) {
        await this._super(...arguments);
        await this._renderCategorySelector(uiFragment);
    },

    async _renderCategorySelector(uiFragment) {
        const categories = await this._fetchCategories();

        for (const cat of categories) {
            this.categoryItems[cat.id] = cat;
        }

        const categorySelectEl = uiFragment.querySelector('[data-name="category_opt"]');
        return this._renderSelectUserValueWidgetButtons(categorySelectEl, this.categoryItems);
    },

    /**
     * Valores por defecto
     */
    _setOptionsDefaultValues() {
        this._setOptionValue("categoryId", "all");
        this._super(...arguments);
    },
});

options.registry.dynamic_snippet_categories = DynamicSnippetCategoriesOptions;

export default DynamicSnippetCategoriesOptions;
