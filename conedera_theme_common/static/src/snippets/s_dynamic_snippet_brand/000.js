/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";
import DynamicSnippetProducts from "@website/snippets/s_dynamic_snippet_carousel/000";

const DynamicSnippetProductsBrand = DynamicSnippetProducts.extend({

    /**
     * Construye el dominio de búsqueda para marcas
     */
    _getBrandSearchDomain() {
        console.log("[DynamicSnippetProductsBrand] _getBrandSearchDomain ejecutado");
        const searchDomain = [];
        let productBrandId = this.$el.get(0).dataset.productBrandId;
        console.log("[DynamicSnippetProductsBrand] Valor de productBrandId:", productBrandId);

        if (productBrandId && productBrandId !== 'all') {
            // Filtramos productos cuyo atributo tenga el valor de marca seleccionado
            searchDomain.push(['attribute_line_ids.value_ids', '=', parseInt(productBrandId)]);
            console.log("[DynamicSnippetProductsBrand] Dominio aplicado:", searchDomain);
        } else {
            console.log("[DynamicSnippetProductsBrand] No se aplica filtro de marca");
        }
        return searchDomain;
    },

    /**
     * Extiende el dominio original del snippet para añadir el filtro de marca
     */
    _getSearchDomain: function () {
        console.log("[DynamicSnippetProductsBrand] _getSearchDomain ejecutado");
        const searchDomain = this._super.apply(this, arguments);
        console.log("[DynamicSnippetProductsBrand] Dominio original:", searchDomain);

        const brandDomain = this._getBrandSearchDomain();
        searchDomain.push(...brandDomain);

        console.log("[DynamicSnippetProductsBrand] Dominio final con marca:", searchDomain);
        return searchDomain;
    },
});

publicWidget.registry.dynamic_snippet_products_brand = DynamicSnippetProductsBrand;

export default DynamicSnippetProductsBrand;
