/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";
import DynamicSnippetCarousel from "@website/snippets/s_dynamic_snippet_carousel/000";

const DynamicSnippetBrand = DynamicSnippetCarousel.extend({
    selector: ".s_dynamic_snippet_brand",

    _getBrandDomain() {
        const brand = this.el.dataset.productBrandId || "all";
        if (brand === "all") {
            return [];
        }
        return [["dr_brand_value_id", "=", parseInt(brand)]];
    },

    _getSearchDomain() {
        const domain = this._super(...arguments);
        domain.push(...this._getBrandDomain());
        return domain;
    },

    _getMainPageUrl() {
        return "/shop";
    },
});

publicWidget.registry.dynamic_snippet_brand = DynamicSnippetBrand;

export default DynamicSnippetBrand;
