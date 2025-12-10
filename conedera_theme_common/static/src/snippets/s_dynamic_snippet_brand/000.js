/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";
import DynamicSnippetProducts from "@website/snippets/s_dynamic_snippet_carousel/000";

const DynamicSnippetProductsBrand = DynamicSnippetProducts.extend({

    _getBrandSearchDomain() {
        console.log("[DynamicSnippetProductsBrand] _getBrandSearchDomain ejecutado");

        let productBrandId = this.$el.get(0)?.dataset.productBrandId;
        console.log("[DynamicSnippetProductsBrand] Valor de productBrandId:", productBrandId);

        const domain = [];

        if (productBrandId && productBrandId !== "all") {
            domain.push(["value_ids", "=", parseInt(productBrandId)]);
            console.log("[DynamicSnippetProductsBrand] Dominio aplicado:", domain);
        } else {
            console.log("[DynamicSnippetProductsBrand] No se aplica filtro de marca");
        }

        return domain;
    },

    /**
     * Extiende el método que arma los parámetros enviados al backend.
     * ¡ESTO ES LO QUE FALTABA!
     */
    _getRequestParams() {
        const params = this._super.apply(this, arguments);

        const productBrandId = this.$el.get(0)?.dataset.productBrandId || "all";

        params.productBrandId = productBrandId;

        console.log("[DynamicSnippetProductsBrand] _getRequestParams enviado al servidor:", params);

        return params;
    },

    /**
     * Extiende el dominio local (solo debug, backend es quien filtra realmente)
     */
    _getSearchDomain() {
        console.log("[DynamicSnippetProductsBrand] _getSearchDomain ejecutado");

        const domain = this._super.apply(this, arguments);
        const brandDomain = this._getBrandSearchDomain();

        domain.push(...brandDomain);

        console.log("[DynamicSnippetProductsBrand] Dominio final:", domain);
        return domain;
    },
});

publicWidget.registry.dynamic_snippet_products_brand = DynamicSnippetProductsBrand;

export default DynamicSnippetProductsBrand;


// ======================================================================
// SNIPPET OPTIONS (EDITOR / BACKEND)
// ======================================================================

import options from "@web_editor/js/editor/snippets.options";

options.registry.dynamic_snippet_products.include({

    init() {
        this._super.apply(this, arguments);
        this.productBrands = {};
        console.log("[dynamic_snippet_products] init ejecutado");
    },

    // -----------------------------
    // Fetch marcas
    // -----------------------------
    _fetchProductBrands() {
        console.log("[dynamic_snippet_products] _fetchProductBrands llamado");

        return this.orm.searchRead(
            "product.attribute.value",
            [["attribute_id.dr_is_brand", "=", true]],
            ["id", "name", "attribute_id"]
        ).then(result => {
            console.log("[dynamic_snippet_products] _fetchProductBrands resultado:", result);
            return result;
        });
    },

    // -----------------------------
    // Render marcas en el panel
    // -----------------------------
    async _renderCustomXML(uiFragment) {
        console.log("[dynamic_snippet_products] _renderCustomXML llamado");

        await this._super.apply(this, arguments);
        await this._renderProductBrandSelector(uiFragment);
    },

    async _renderProductBrandSelector(uiFragment) {
        console.log("[dynamic_snippet_products] _renderProductBrandSelector llamado");

        const productBrands = await this._fetchProductBrands();

        for (let b of productBrands) {
            this.productBrands[b.id] = b;
        }

        console.log("[dynamic_snippet_products] Marcas procesadas:", this.productBrands);

        const selector = uiFragment.querySelector('[data-name="product_brand_opt"]');
        console.log("[dynamic_snippet_products] Selector encontrado:", selector);

        return this._renderSelectUserValueWidgetButtons(selector, this.productBrands);
    },

    // -----------------------------
    // Default options
    // -----------------------------
    _setOptionsDefaultValues() {
        console.log("[dynamic_snippet_products] _setOptionsDefaultValues llamado");

        this._setOptionValue("productBrandId", "all");

        this._super.apply(this, arguments);
        console.log("[dynamic_snippet_products] Valor por defecto productBrandId = all");
    },
});

// /** @odoo-module **/

// import publicWidget from "@web/legacy/js/public/public_widget";
// import DynamicSnippetProducts from "@website/snippets/s_dynamic_snippet_carousel/000";

// const DynamicSnippetProductsBrand = DynamicSnippetProducts.extend({

//     /**
//      * Construye el dominio de búsqueda para marcas
//      */
//     _getBrandSearchDomain() {
//         console.log("[DynamicSnippetProductsBrand] _getBrandSearchDomain ejecutado");
//         const searchDomain = [];
//         let productBrandId = this.$el.get(0).dataset.productBrandId;
//         console.log("[DynamicSnippetProductsBrand] Valor de productBrandId:", productBrandId);

//         if (productBrandId && productBrandId !== 'all') {
//             // Usamos el campo estándar value_ids de product.template
//             searchDomain.push(['value_ids', '=', parseInt(productBrandId)]);
//             console.log("[DynamicSnippetProductsBrand] Dominio aplicado:", searchDomain);
//         } else {
//             console.log("[DynamicSnippetProductsBrand] No se aplica filtro de marca");
//         }
//         return searchDomain;
//     },

//     /**
//      * Extiende el dominio original del snippet para añadir el filtro de marca
//      */
//     _getSearchDomain: function () {
//         console.log("[DynamicSnippetProductsBrand] _getSearchDomain ejecutado");
//         const searchDomain = this._super.apply(this, arguments);
//         console.log("[DynamicSnippetProductsBrand] Dominio original:", searchDomain);

//         const brandDomain = this._getBrandSearchDomain();
//         searchDomain.push(...brandDomain);

//         console.log("[DynamicSnippetProductsBrand] Dominio final con marca:", searchDomain);
//         return searchDomain;
//     },
// });

// publicWidget.registry.dynamic_snippet_products_brand = DynamicSnippetProductsBrand;

// export default DynamicSnippetProductsBrand;
