/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";
import DynamicSnippetCarousel from "@website/snippets/s_dynamic_snippet_carousel/000";

const DynamicSnippetBrand = DynamicSnippetCarousel.extend({
    selector: ".s_dynamic_snippet_brand",

    // Sobrescribimos para llamar al controlador en vez de server action
    async _fetchData() {
        const brandId = this.el.dataset.productBrandId || "all";

        const products = await this._rpc({
            route: "/snippet/products_by_brand",
            params: {
                brand_id: brandId,
                limit: 16,
            },
        });

        return products;
    },

    // Renderizamos los productos recibidos
    async start() {
        await this._super(...arguments);
        const products = await this._fetchData();

        // Aquí puedes usar tu propio método de renderizado
        // o dejar que el DynamicSnippetCarousel maneje los records
        this._renderProducts(products);
    },
});

publicWidget.registry.dynamic_snippet_brand = DynamicSnippetBrand;
export default DynamicSnippetBrand;

// /** @odoo-module **/

// import publicWidget from "@web/legacy/js/public/public_widget";
// import DynamicSnippetProducts from "@website/snippets/s_dynamic_snippet_products/000";

// const DynamicSnippetProductsBrand = DynamicSnippetProducts.extend({

//     /**
//      * Gets the brand search domain
//      *
//      * @private
//      */
//     _getBrandSearchDomain() {
//         const searchDomain = [];
//         let productBrandId = this.$el.get(0).dataset.productBrandId;
//         if (productBrandId && productBrandId !== 'all') {
//             // 🔹 Ahora filtramos por el campo dr_brand_value_id
//             searchDomain.push(['dr_brand_value_id', '=', parseInt(productBrandId)]);
//         }
//         return searchDomain;
//     },

//     /**
//      * Override search domain to include brand
//      *
//      * @override
//      * @private
//      */
//     _getSearchDomain: function () {
//         const searchDomain = this._super.apply(this, arguments);
//         searchDomain.push(...this._getBrandSearchDomain());
//         return searchDomain;
//     },
// });

// publicWidget.registry.dynamic_snippet_products_brand = DynamicSnippetProductsBrand;

// export default DynamicSnippetProductsBrand;

