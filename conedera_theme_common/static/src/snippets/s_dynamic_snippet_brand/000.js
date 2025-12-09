/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";
import DynamicSnippetProducts from "website.snippets.s_dynamic_snippet_products.000";

const DynamicSnippetProductsBrand = DynamicSnippetProducts.extend({

    _getSearchContext: function () {
        const searchContext = this._super.apply(this, arguments);
        let productBrandId = this.$el.get(0).dataset.productBrandId;
        if (productBrandId && productBrandId !== 'all') {
            searchContext.product_brand_id = parseInt(productBrandId);
        }
        return searchContext;
    },
});

publicWidget.registry.dynamic_snippet_products = DynamicSnippetProductsBrand;

export default DynamicSnippetProductsBrand;

// /** @odoo-module **/

// import publicWidget from "@web/legacy/js/public/public_widget";
// import { rpc } from "@web/core/network/rpc";
// import DynamicSnippetCarousel from "@website/snippets/s_dynamic_snippet_carousel/000";
// import wSaleUtils from "@website_sale/js/website_sale_utils";
// import { WebsiteSale } from "../../js/website_sale";

// const DynamicSnippetBrands = DynamicSnippetCarousel.extend({
//     selector: '.s_dynamic_snippet_brand',

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
//             product_brand_id: this.$el.get(0).dataset.productBrandId || undefined,
            
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
// publicWidget.registry.dynamic_snippet_brand = DynamicSnippetBrands;

// export default DynamicSnippetBrands;
