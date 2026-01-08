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

        // Enfoque 1: vista simple (móvil vs escritorio)
        if (!tplKey) {
            options.chunkSize = uiUtils.isSmall() ? 2 : 6;
        }
        // Enfoque 2: estilo especial con template style_2
        else if (tplKey.includes("dynamic_filter_template_product_product_style_2")) {
            if (uiUtils.isSmall()) {
                options.chunkSize = this.editableMode ? 1 : 2;
            } else {
                options.chunkSize = 4;
            }
        }
        // Fallback por si aparece otro template
        else {
            options.chunkSize = uiUtils.isSmall() ? 2 : 4;
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
