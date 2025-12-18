/** @odoo-module **/
import publicWidget from "@web/legacy/js/public/public_widget";
import DynamicSnippetProducts from "@website_sale/snippets/s_dynamic_snippet_products/000";
import { utils as uiUtils } from "@web/core/ui/ui_service";

const DynamicSnippetProductsCombined = DynamicSnippetProducts.extend({

    // Controla cuántos productos se muestran por slide
    _getQWebRenderOptions() {
        const options = this._super(...arguments);
        const tplKey = this.$el.data("template-key");

        if (
            (this.editableMode && uiUtils.isSmall()) ||
            (tplKey &&
             tplKey.includes("dynamic_filter_template_product_product_style_2") &&
             uiUtils.isSmall())
        ) {
            options.chunkSize = 1;
        } else {
            options.chunkSize = uiUtils.isSmall() ? 2 : 4;
        }

        return options;
    },

    // Define el dominio de búsqueda de productos
    _getSearchDomain() {
        const domain = this._super(...arguments);
        const brandDomain = this._getBrandSearchDomain();
        domain.push(...brandDomain);
        return domain;
    },

    // Construye el filtro por marca
    _getBrandSearchDomain() {
        let brandId = this.$el.get(0).dataset.productBrandId;
        if (!brandId || brandId === "all") {
            return [];
        }
        return [["attribute_line_ids.value_ids", "in", [parseInt(brandId)]]];
    },
});

publicWidget.registry.dynamic_snippet_products = DynamicSnippetProductsCombined;
export default DynamicSnippetProductsCombined;
