/** @odoo-module **/
import publicWidget from "@web/legacy/js/public/public_widget";
import DynamicSnippetProducts from "@website_sale/snippets/s_dynamic_snippet_products/000";
import { utils as uiUtils } from "@web/core/ui/ui_service";

const DynamicSnippetProductsExtended = DynamicSnippetProducts.extend({

    _getQWebRenderOptions() {
        const options = this._super.apply(this, arguments);

        if (this.templateKey === 'dynamic_filter_template_product_product_style_2') {
            if (uiUtils.isSmall()) {
                options.chunkSize = 1; // mobile: 1 producto
            } else {
                options.chunkSize = 4;
            }
        } else {
            if (uiUtils.isSmall()) {
                options.chunkSize = 2;
            } else {
                options.chunkSize = 4;
            }
        }

        return options;
    },
});

publicWidget.registry.dynamic_snippet_products = DynamicSnippetProductsExtended;

export default DynamicSnippetProductsExtended;


// /** @odoo-module **/
// import publicWidget from "@web/legacy/js/public/public_widget";
// import DynamicSnippetProducts from "@website_sale/snippets/s_dynamic_snippet_products/000";
// import { utils as uiUtils } from "@web/core/ui/ui_service";

// const DynamicSnippetProductsExtended = DynamicSnippetProducts.extend({
//     /**
//      * @override
//      */

//         _getQWebRenderOptions() {
//         const options = this._super.apply(this, arguments);
//         if (uiUtils.isSmall()) {
//             options.chunkSize = 2; //vista de productos mobil
//         } else {
//             options.chunkSize = 4;// cantidad de productos web/escritorio
//         }
//         return options;
//     },
// });

// // Se sobreescribe el registro original
// publicWidget.registry.dynamic_snippet_products = DynamicSnippetProductsExtended;

// export default DynamicSnippetProductsExtended;
