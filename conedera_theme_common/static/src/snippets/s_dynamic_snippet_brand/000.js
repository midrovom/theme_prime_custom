/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";
import DynamicSnippetProducts from "@website/snippets/s_dynamic_snippet_carousel/000";

console.log("%c[DynamicSnippetProductsBrand] Archivo cargado", "color: green; font-weight: bold;");

const DynamicSnippetProductsBrand = DynamicSnippetProducts.extend({

    /**
     * INICIO SNIPPET FRONTEND
     * (se ejecuta en el sitio web, no en el editor)
     */

    start() {
        console.log("%c[DynamicSnippetProductsBrand] start()", "color: #00bfff");
        return this._super(...arguments);
    },

    /**
     * Construye el dominio base + dominio por marca
     */
    _getSearchDomain: function () {
        console.log("%c[DynamicSnippetProductsBrand] _getSearchDomain ejecutado", "color: orange");

        const searchDomain = this._super.apply(this, arguments);
        console.log("[DynamicSnippetProductsBrand] Dominio original:", JSON.stringify(searchDomain));

        const brandDomain = this._getBrandSearchDomain();
        console.log("[DynamicSnippetProductsBrand] Dominio generado por marca:", JSON.stringify(brandDomain));

        searchDomain.push(...brandDomain);

        console.log("%c[DynamicSnippetProductsBrand] Dominio final:", "color: yellow", JSON.stringify(searchDomain));
        return searchDomain;
    },

    /**
     * Dominio para filtrar por marca
     */
    _getBrandSearchDomain: function () {
        console.log("%c[DynamicSnippetProductsBrand] _getBrandSearchDomain()", "color: purple");

        const brandId = this.options.productBrandId;
        console.log("[DynamicSnippetProductsBrand] Marca seleccionada:", brandId);

        if (!brandId || brandId === "all") {
            console.log("[DynamicSnippetProductsBrand] Marca = all → No filtrar");
            return [];
        }

        const idInt = parseInt(brandId);
        if (isNaN(idInt)) {
            console.warn("[DynamicSnippetProductsBrand] ERROR: brandId no es entero:", brandId);
            return [];
        }

        const domain = [
            ["attribute_line_ids.value_ids", "in", [idInt]]
        ];

        console.log("[DynamicSnippetProductsBrand] Dominio construido:", domain);
        return domain;
    },
});

publicWidget.registry.dynamic_snippet_products_brand = DynamicSnippetProductsBrand;

export default DynamicSnippetProductsBrand;
