/** @odoo-module **/

import DynamicSnippetCarousel from "@website/snippets/s_dynamic_snippet_carousel/000";

const DynamicSnippetBrand = DynamicSnippetCarousel.extend({

    selector: '.s_dynamic_snippet_brand',

    /**
     * Add domain to filter products by brand attribute value
     */
    _getSearchDomain() {
        const domain = this._super(...arguments);

        const brandId = this.el.dataset.brandId;

        if (brandId && brandId !== "all") {
            domain.push([
                "product.product_attribute_value_id",
                "=",
                parseInt(brandId)
            ]);
        }

        return domain;
    },

    _getMainPageUrl() {
        return "/shop";
    },
});

export default DynamicSnippetBrand;
