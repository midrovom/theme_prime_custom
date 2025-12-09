
// /** @odoo-module **/

// import publicWidget from "@web/legacy/js/public/public_widget";
// import DynamicSnippetProducts from "@website/snippets/s_dynamic_snippet_products/000";  // importa el original

// // Extendemos el snippet original
// const DynamicSnippetProductsBrand = DynamicSnippetProducts.extend({

//     /**
//      * Nuevo método para filtrar por marca
//      */
//     _getBrandSearchDomain() {
//         const searchDomain = [];
//         let productBrandId = this.$el.get(0).dataset.productBrandId;
//         if (productBrandId && productBrandId !== 'all') {
//             searchDomain.push(['dr_brand_value_id', '=', parseInt(productBrandId)]);
//         }
//         return searchDomain;
//     },

//     /**
//      * Sobrescribimos el searchDomain para incluir marcas
//      */
//     _getSearchDomain: function () {
//         const searchDomain = this._super.apply(this, arguments);
//         searchDomain.push(...this._getBrandSearchDomain());
//         return searchDomain;
//     },
// });

// // Registramos el nuevo widget en el mismo selector
// publicWidget.registry.dynamic_snippet_products = DynamicSnippetProductsBrand;

// export default DynamicSnippetProductsBrand;
