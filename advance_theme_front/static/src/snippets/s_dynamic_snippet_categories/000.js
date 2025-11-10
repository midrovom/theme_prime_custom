/** @odoo-module **/
import publicWidget from "@web/legacy/js/public/public_widget";
import DynamicSnippetCarousel from "@website/snippets/s_dynamic_snippet_carousel/000";

const DynamicSnippetCategories = DynamicSnippetCarousel.extend({
    selector: ".s_dynamic_snippet_categories",

    _getSearchDomain() {
        const searchDomain = [];
        // Siempre traemos solo categorías públicas
        searchDomain.push(['website_published', '=', true]);
        return searchDomain;
    },

    _getRpcParameters() {
        return this._super(...arguments);
    }


});

publicWidget.registry.dynamic_snippet_categories = DynamicSnippetCategories;
