/** @odoo-module **/
import publicWidget from "@web/legacy/js/public/public_widget";
import DynamicSnippetProducts from "@website_sale/snippets/s_dynamic_snippet_products/000";
import { utils as uiUtils } from "@web/core/ui/ui_service";

const DynamicSnippetProductsExtended = DynamicSnippetProducts.extend({
    _getQWebRenderOptions() {
        const options = this._super(...arguments);

        // Leer el template-key directamente del DOM
        const tplKey = this.$el.data("template-key");
        console.log("template-key detectado:", tplKey);

        // Si es tu template y es móvil → forzar 1 producto por slide
        if (
            tplKey &&
            tplKey.includes("dynamic_filter_template_product_product_style_2") &&
            uiUtils.isSmall()
        ) {
            options.chunkSize = 1;
        } else {
            options.chunkSize = uiUtils.isSmall() ? 2 : 4;
        }

        return options;
    },
});

publicWidget.registry.dynamic_snippet_products = DynamicSnippetProductsExtended;
export default DynamicSnippetProductsExtended;
