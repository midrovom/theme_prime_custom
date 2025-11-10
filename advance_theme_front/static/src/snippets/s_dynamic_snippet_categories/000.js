/** @odoo-module **/
import publicWidget from "@web/legacy/js/public/public_widget";
import DynamicSnippetCarousel from "@website/snippets/s_dynamic_snippet_carousel/000";

const DynamicSnippetCategories = DynamicSnippetCarousel.extend({
    selector: ".s_dynamic_snippet_categories",

    _getSearchDomain() {
        console.log("MOSTRANDO GET SEARCH DOMAIN");
        // Aquí puedes devolver [] o algún filtro por categoría si quieres
        return [];
    },

    _getRpcParameters() {
        console.log("MOSTRANDO GET RPC PARAMETERS");
        return {}; // No necesitas parámetros especiales de momento
    },

    _getMainPageUrl() {
        console.log("MOSTRANDO GET MAIN PAGE URL");
        return "/shop";
    },

});

publicWidget.registry.dynamic_snippet_categories = DynamicSnippetCategories;
