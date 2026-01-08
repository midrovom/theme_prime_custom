/** @odoo-module **/
import publicWidget from "@web/legacy/js/public/public_widget";
import DynamicSnippetProducts from "@website_sale/snippets/s_dynamic_snippet_products/000";
import { utils as uiUtils } from "@web/core/ui/ui_service";

const DynamicSnippetProductsUnified = DynamicSnippetProducts.extend({

    /**
     * Controla cuántos productos se muestran por slide
     * según el tamaño de pantalla y el template.
     * Aquí se combinan ambos enfoques en un solo registro.
     */
    _getQWebRenderOptions() {
        const options = this._super(...arguments);
        const tplKey = this.$el.data("template-key");

        if (uiUtils.isSmall()) {
            // Vista móvil
            if (tplKey && tplKey.includes("dynamic_filter_template_product_product_style_2")) {
                options.chunkSize = 1; // estilo 2 → 1 producto en móvil
            } else {
                options.chunkSize = 2; // otros → 2 productos en móvil
            }
        } else {
            // Vista escritorio
            if (tplKey && tplKey.includes("dynamic_filter_template_product_product_style_2")) {
                options.chunkSize = 4; // estilo 2 → 4 productos en escritorio
            } else if (tplKey && tplKey.includes("dynamic_filter_template_product_product_style_1")) {
                options.chunkSize = 4; // estilo 1 → 4 productos en escritorio
            } else {
                options.chunkSize = 6; // otros → 6 productos en escritorio
            }
        }

        return options;
    },

    /**
     * Define el dominio de búsqueda de productos
     * incluyendo filtro por marca.
     */
    _getSearchDomain() {
        const domain = this._super(...arguments);
        const brandDomain = this._getBrandSearchDomain();
        domain.push(...brandDomain);
        return domain;
    },

    /**
     * Construye el filtro por marca a partir del dataset.
     */
    _getBrandSearchDomain() {
        let brandId = this.$el.get(0).dataset.productBrandId;
        if (!brandId || brandId === "all") {
            return [];
        }
        return [["attribute_line_ids.value_ids", "in", [parseInt(brandId)]]];
    },
});

// Un solo registro para el snippet
publicWidget.registry.dynamic_snippet_products = DynamicSnippetProductsUnified;

export default DynamicSnippetProductsUnified;
