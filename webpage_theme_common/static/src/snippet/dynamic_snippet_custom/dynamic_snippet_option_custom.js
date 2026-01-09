
/** @odoo-module **/
import options from "@web_editor/js/editor/snippets.options";
import { utils as uiUtils } from "@web/core/ui/ui_service";

options.registry.dynamic_snippet_products.include({
    _getQWebRenderOptions() {
        const options = this._super(...arguments);
        const tplKey = this.$target.data("template-key");

        //  Builder → siempre 1 producto en estilo 2, incluso con datos ficticios
        if (this.editableMode && tplKey && tplKey.includes("dynamic_filter_template_product_product_style_2")) {
            options.chunkSize = 1;
        }

        // Frontend móvil → también 1 producto por slide
        if (uiUtils.isSmall()) {
            options.chunkSize = 1;
        }

        return options;
    },
});

// /** @odoo-module **/
// import options from "@web_editor/js/editor/snippets.options";

// options.registry.dynamic_snippet_products.include({
//     _getQWebRenderOptions() {
//         const options = this._super(...arguments);
//         const tplKey = this.$target.data("template-key");

//         if (this.editableMode && tplKey && tplKey.includes("dynamic_filter_template_product_product_style_2")) {
//             options.chunkSize = 1; // builder → siempre 1 producto
//         }
//         return options;
//     },
// });
