/** @odoo-module **/
import options from "@web_editor/js/editor/snippets.options";

options.registry.dynamic_snippet_products.include({
    _getQWebRenderOptions() {
        const options = this._super(...arguments);
        const tplKey = this.$target.data("template-key");

        if (this.editableMode && tplKey && tplKey.includes("dynamic_filter_template_product_product_style_2")) {
            options.chunkSize = 1; // builder → siempre 1 producto
        }
        return options;
    },
});



// /** @odoo-module **/
// import publicWidget from "@web/legacy/js/public/public_widget";
// import DynamicSnippetProducts from "@website_sale/snippets/s_dynamic_snippet_products/000";

// const DynamicSnippetProductsWysiwyg = DynamicSnippetProducts.extend({
//     _getQWebRenderOptions() {
//         const options = this._super(...arguments);
//         const tplKey = this.$el.data("template-key");

//         // 🔑 Lógica especial para el builder
//         if (this.editableMode && tplKey && tplKey.includes("dynamic_filter_template_product_product_style_2")) {
//             options.chunkSize = 1; // siempre 1 producto en builder
//         }

//         return options;
//     },
// });

// publicWidget.registry.dynamic_snippet_products = DynamicSnippetProductsWysiwyg;
// export default DynamicSnippetProductsWysiwyg;