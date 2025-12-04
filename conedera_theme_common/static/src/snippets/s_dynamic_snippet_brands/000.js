/** @odoo-module **/
import publicWidget from "@web/legacy/js/public/public_widget";
import DynamicSnippetCarousel from "@website/snippets/s_dynamic_snippet_carousel/000";
import { utils as uiUtils } from "@web/core/ui/ui_service";

const DynamicSnippetCategories = DynamicSnippetCarousel.extend({
    selector: ".s_dynamic_snippet_categories",

    /**
     * @override
     * @private
     */
    _getMainPageUrl() {
        return "/shop";
    },

    /**
     * @override
     * @private
     */
    _getQWebRenderOptions: function () {
        const options = this._super.apply(this, arguments);

        if (uiUtils.isSmall()) {
            options.chunkSize = 2; //cantidad movil
        }else {
            options.chunkSize = 4; // cantidad de productos web/escritorio
        }

        return options;
    },
});

publicWidget.registry.dynamic_snippet_categories = DynamicSnippetCategories;

export default DynamicSnippetCategories;