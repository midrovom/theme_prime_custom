/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";
import DynamicSnippetCarousel from "@website/snippets/s_dynamic_snippet_carousel/000";

const DynamicSnippetBrand = DynamicSnippetCarousel.extend({
    selector: ".s_dynamic_snippet_brand",

    _getSearchDomain() {
        const domain = this._super(...arguments);
        const brand = this.el.dataset.product_brand_id || "all";

        if (brand !== "all") {
            domain.push(["dr_brand_value_id", "=", parseInt(brand)]);
        }

        this.options.context = this.options.context || {};
        this.options.context.product_brand_id = brand;
        this.options.context.mode = "by_brand";

        return domain;
    },

    _getDynamicFilterContext() {
        const ctx = this._super(...arguments) || {};
        const brand = this.el.dataset.product_brand_id || "all";

        ctx.product_brand_id = brand;
        ctx.mode = "by_brand";

        return ctx;
    },

    _getDynamicFilterData() {
        const data = this._super(...arguments) || {};
        const brand = this.el.dataset.product_brand_id || "all";

        data.product_brand_id = brand;
        data.mode = "by_brand";

        return data;
    },

    _getMainPageUrl() {
        return "/shop";
    },
});

publicWidget.registry.dynamic_snippet_brand = DynamicSnippetBrand;
export default DynamicSnippetBrand;



// /** @odoo-module **/

// import publicWidget from "@web/legacy/js/public/public_widget";
// import { rpc } from "@web/core/network/rpc";
// import DynamicSnippetCarousel from "@website/snippets/s_dynamic_snippet_carousel/000";
// import wSaleUtils from "@website_sale/js/website_sale_utils";
// import { WebsiteSale } from "../../js/website_sale";

// const DynamicSnippetBrands = DynamicSnippetCarousel.extend({
//     selector: '.s_dynamic_snippet_brands',

//     //--------------------------------------------------------------------------
//     // Private
//     //--------------------------------------------------------------------------

//     /**
//      * Gets the brand search domain
//      *
//      * @private
//      */
//     _getBrandSearchDomain() {
//         const searchDomain = [];
//         let productBrandId = this.$el.get(0).dataset.productBrandId;
//         if (productBrandId && productBrandId !== 'all') {
//             searchDomain.push(['dr_brand_value_id', '=', parseInt(productBrandId)]);
//         }
//         return searchDomain;
//     },

//     /**
//      * @override
//      * @private
//      */
//     _getSearchDomain: function () {
//         const searchDomain = this._super.apply(this, arguments);
//         searchDomain.push(...this._getBrandSearchDomain());
//         return searchDomain;
//     },

//     /**
//      * @override
//      * @private
//      */
//     _getRpcParameters: function () {
//         return Object.assign(this._super.apply(this, arguments), {
//             productBrandId: this.$el.get(0).dataset.productBrandId || undefined,
//         });
//     },

//     /**
//      * @override
//      * @private
//      */
//     _getMainPageUrl() {
//         return "/shop";
//     },
// });

// const DynamicSnippetBrandsCard = WebsiteSale.extend({
//     selector: '.o_carousel_product_card',
//     read_events: {
//         'click .js_add_cart': '_onClickAddToCart',
//     },

//     init(root, options) {
//         const parent = options.parent || root;
//         this._super(parent, options);
//     },

//     start() {
//         this.add2cartRerender = this.el.dataset.add2cartRerender === 'True';
//     },

//     //--------------------------------------------------------------------------
//     // Handlers
//     //--------------------------------------------------------------------------

//     /**
//      * Event triggered by a click on the Add to cart button
//      *
//      * @param {OdooEvent} ev
//      */
//     async _onClickAddToCart(ev) {
//         const button = ev.currentTarget;
//         const data = await rpc("/shop/cart/update_json", {
//             product_id: parseInt(button.dataset.productId),
//             add_qty: 1,
//             display: false,
//         });
//         wSaleUtils.updateCartNavBar(data);
//         wSaleUtils.showCartNotification(this.call.bind(this), data.notification_info);

//         if (this.add2cartRerender) {
//             this.trigger_up('widgets_start_request', {
//                 $target: this.$el.closest('.s_dynamic'),
//             });
//         }
//     },
// });

// publicWidget.registry.dynamic_snippet_brands_cta = DynamicSnippetBrandsCard;
// publicWidget.registry.dynamic_snippet_brands = DynamicSnippetBrands;

// export default DynamicSnippetBrands;
