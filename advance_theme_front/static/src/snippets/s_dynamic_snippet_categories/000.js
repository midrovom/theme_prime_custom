/** @odoo-module **/
import publicWidget from "@web/legacy/js/public/public_widget";
import DynamicSnippetCarousel from "@website/snippets/s_dynamic_snippet_carousel/000";

const DynamicSnippetCategories = DynamicSnippetCarousel.extend({
    selector: ".s_dynamic_snippet_categories",

    /**
     * @override
     * @private
     */
    _getMainPageUrl() {
        return "/shop";
    },


});

publicWidget.registry.dynamic_snippet_categories = DynamicSnippetCategories;

export default DynamicSnippetCategories;
