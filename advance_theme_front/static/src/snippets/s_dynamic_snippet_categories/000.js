/** @odoo-module **/
import publicWidget from "@web/legacy/js/public/public_widget";
import DynamicSnippetCarousel from "@website/snippets/s_dynamic_snippet_carousel/000";

const DynamicSnippetCategories = DynamicSnippetCarousel.extend({
    selector: ".s_dynamic_snippet_categories",

    init() {
        this._super.apply(this, arguments);
        this.isAlternativeProductSnippet = false; // asegura que filter_opt se muestre
    },
    _getCategorySearchDomain() {
        // aquí defines cómo tu snippet de categorías filtra registros
        return [];
    }


});

publicWidget.registry.dynamic_snippet_categories = DynamicSnippetCategories;


export default DynamicSnippetCategories;

