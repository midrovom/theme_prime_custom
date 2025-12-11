/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";

publicWidget.registry.dynamic_snippet_products.include({

    /**
     * Extiende el dominio original del snippet para añadir el filtro de marca
     */
    _getSearchDomain: function () {
        console.log("[DynamicSnippetProductsBrand] _getSearchDomain ejecutado");
        const searchDomain = this._super.apply(this, arguments);
        console.log("[DynamicSnippetProductsBrand] Dominio original:", searchDomain);

        const productBrandId = this.$el.get(0).dataset.productBrandId;
        if (productBrandId && productBrandId !== 'all') {
            searchDomain.push(['dr_brand_value_id', '=', parseInt(productBrandId)]);
        }

        console.log("[DynamicSnippetProductsBrand] Dominio final con marca:", searchDomain);
        return searchDomain;
    },
});
