/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";
import DynamicSnippet from "@website/snippets/s_dynamic_snippet/000";

console.log("%c[DynamicSnippetProductsBrand] Archivo cargado", "color: green; font-weight: bold;");

const DynamicSnippetProductsBrand = DynamicSnippet.extend({

    selector: ".s_dynamic_snippet_products",

    _getSearchDomain() {
        console.log("%c[DynamicSnippetProductsBrand] _getSearchDomain ejecutado", "color: orange");

        const domain = this._super(...arguments);
        console.log("[DynamicSnippetProductsBrand] Dominio original:", domain);

        console.log("OPTIONS COMPLETAS:", this.options);

        const brandDomain = this._getBrandSearchDomain();
        console.log("[DynamicSnippetProductsBrand] Dominio marca:", brandDomain);

        domain.push(...brandDomain);

        console.log("%c[DynamicSnippetProductsBrand] Dominio final:", "color: yellow", domain);
        return domain;
    },

    _getBrandSearchDomain() {
        console.log("%c[DynamicSnippetProductsBrand] _getBrandSearchDomain()", "color: purple");

        const brandId = this.options["product-brand-id"];
        console.log("[DynamicSnippetProductsBrand] brandId REAL:", brandId);

        if (!brandId || brandId === "all") {
            console.log("[DynamicSnippetProductsBrand] Marca = all → Sin filtro");
            return [];
        }

        const idInt = parseInt(brandId);
        return [
            ["attribute_line_ids.value_ids", "in", [idInt]]
        ];
    },
});

publicWidget.registry.DynamicSnippetProductsBrand = DynamicSnippetProductsBrand;

export default DynamicSnippetProductsBrand;
