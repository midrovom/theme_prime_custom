/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";
import DynamicSnippet from "@website/snippets/s_dynamic_snippet/000";

console.log("%c[DynamicSnippetProductsBrand] Archivo cargado", "color: green; font-weight: bold;");

const DynamicSnippetProductsBrand = DynamicSnippet.extend({

    selector: ".s_dynamic_snippet_products",  

    /**
     * DOMINIO FINAL DE PRODUCTOS
     */
    _getSearchDomain: function () {
        console.log("%c[DynamicSnippetProductsBrand] _getSearchDomain ejecutado", "color: orange");

        const domain = this._super(...arguments);
        console.log("[DynamicSnippetProductsBrand] Dominio original:", domain);

        const brandDomain = this._getBrandSearchDomain();
        console.log("[DynamicSnippetProductsBrand] Dominio marca:", brandDomain);

        domain.push(...brandDomain);

        console.log("%c[DynamicSnippetProductsBrand] Dominio final:", "color: yellow", domain);
        return domain;
    },

    /**
     * FILTRAR POR MARCA
     */
    _getBrandSearchDomain() {
        console.log("%c[DynamicSnippetProductsBrand] _getBrandSearchDomain()", "color: purple");

        const brandId = this.options.productBrandId;
        console.log("[DynamicSnippetProductsBrand] brandId:", brandId);

        if (!brandId || brandId === "all") return [];

        const idInt = parseInt(brandId);

        return [
            ["attribute_line_ids.value_ids", "=", idInt]
        ];
    },
});

publicWidget.registry.DynamicSnippetProductsBrand = DynamicSnippetProductsBrand;

export default DynamicSnippetProductsBrand;
