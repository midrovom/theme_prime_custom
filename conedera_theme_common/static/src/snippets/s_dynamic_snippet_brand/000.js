/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";
import DynamicSnippetCarousel from "@website/snippets/s_dynamic_snippet_carousel/000";

const DynamicSnippetBrand = DynamicSnippetCarousel.extend({
    selector: ".s_dynamic_snippet_brand",

    _getSearchDomain() {
        const domain = this._super(...arguments);

        const brand = this.el.dataset.productBrandId || "all";

        if (brand !== "all") {
            domain.push(["dr_brand_value_id", "=", parseInt(brand)]);
        }

        // Enviar SIEMPRE los 2 nombres (camelCase + snake_case)
        this.options.context = this.options.context || {};
        this.options.context.productBrandId = brand;      // JS original
        this.options.context.product_brand_id = brand;    // requerido por backend
        this.options.context.mode = "by_brand";

        return domain;
    },

    _getDynamicFilterContext() {
        const ctx = this._super(...arguments) || {};

        const brand = this.el.dataset.productBrandId || "all";

        // Igual enviamos ambas variantes
        ctx.productBrandId = brand;
        ctx.product_brand_id = brand;
        ctx.mode = "by_brand";

        return ctx;
    },

    _getMainPageUrl() {
        return "/shop";
    },
});

publicWidget.registry.dynamic_snippet_brand = DynamicSnippetBrand;

export default DynamicSnippetBrand;
