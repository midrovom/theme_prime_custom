/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";
import DynamicSnippetProducts from "@website/snippets/s_dynamic_snippet_products/000";

console.log("%c[DynamicSnippetProductsBrand] Archivo cargado", "color: green; font-weight: bold;");

const DynamicSnippetProductsBrand = DynamicSnippetProducts.extend({

    _getSearchDomain() {
        console.log("%c[DynamicSnippetProductsBrand] _getSearchDomain ejecutado", "color: orange");

        const domain = this._super(...arguments);

        const brandDomain = this._getBrandSearchDomain();
        console.log("[DynamicSnippetProductsBrand] Dominio marca:", brandDomain);

        domain.push(...brandDomain);

        console.log("%c[DynamicSnippetProductsBrand] Dominio final:", "color: yellow", domain);
        return domain;
    },

    _getBrandSearchDomain() {
        console.log("%c[DynamicSnippetProductsBrand] _getBrandSearchDomain()", "color: purple");

        // LEEMOS EL ATRIBUTO IGUAL QUE LA CATEGORÍA
        let brandId = this.$el.get(0).dataset.productBrandId;

        console.log("[DynamicSnippetProductsBrand] brandId:", brandId);

        if (!brandId || brandId === 'all') {
            return [];
        }

        brandId = parseInt(brandId);

        return [
            ["attribute_line_ids.value_ids", "in", [brandId]]
        ];
    },
});

publicWidget.registry.dynamic_snippet_products_brand = DynamicSnippetProductsBrand;

export default DynamicSnippetProductsBrand;
