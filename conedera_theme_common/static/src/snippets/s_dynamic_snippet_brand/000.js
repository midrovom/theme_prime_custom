/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";
import { rpc } from "@web/core/network/rpc";
import DynamicSnippetCarousel from "@website/snippets/s_dynamic_snippet_carousel/000";
import wSaleUtils from "@website_sale/js/website_sale_utils";
import { WebsiteSale } from "../../js/website_sale";

const DynamicSnippetProducts = DynamicSnippetCarousel.extend({
    selector: '.s_dynamic_snippet_products',

    //--------------------------------------------------------------------------
    // Private
    //--------------------------------------------------------------------------

    /**
     * Gets the category search domain
     *
     * @private
     */
    _getCategorySearchDomain() {
        const searchDomain = [];
        let productCategoryId = this.$el.get(0).dataset.productCategoryId;
        if (productCategoryId && productCategoryId !== 'all') {
            if (productCategoryId === 'current') {
                productCategoryId = undefined;
                const productCategoryField = $("#product_details").find(".product_category_id");
                if (productCategoryField && productCategoryField.length) {
                    productCategoryId = parseInt(productCategoryField[0].value);
                }
                if (!productCategoryId) {
                    this.trigger_up('main_object_request', {
                        callback: function (value) {
                            if (value.model === "product.public.category") {
                                productCategoryId = value.id;
                            }
                        },
                    });
                }
                if (!productCategoryId) {
                    const productTemplateId = $("#product_details").find(".product_template_id");
                    if (productTemplateId && productTemplateId.length) {
                        searchDomain.push(['public_categ_ids.product_tmpl_ids', '=', parseInt(productTemplateId[0].value)]);
                    }
                }
            }
            if (productCategoryId) {
                searchDomain.push(['public_categ_ids', 'child_of', parseInt(productCategoryId)]);
            }
        }
        return searchDomain;
    },

    /**
     * Gets the tag search domain
     *
     * @private
     */
    _getTagSearchDomain() {
        const searchDomain = [];
        let productTagIds = this.$el.get(0).dataset.productTagIds;
        productTagIds = productTagIds ? JSON.parse(productTagIds) : [];
        if (productTagIds.length) {
            searchDomain.push(['all_product_tag_ids', 'in', productTagIds.map(productTag => productTag.id)]);
        }
        return searchDomain;
    },

    /**
     * 🔹 Gets the brand search domain
     *
     * @private
     */
    _getBrandSearchDomain() {
        const searchDomain = [];
        let productBrandId = this.$el.get(0).dataset.productBrandId;
        if (productBrandId && productBrandId !== 'all') {
            searchDomain.push(['dr_brand_value_id', '=', parseInt(productBrandId)]);
        }
        return searchDomain;
    },

    /**
     * Method to be overridden in child components in order to provide a search
     * domain if needed.
     * @override
     * @private
     */
    _getSearchDomain: function () {
        const searchDomain = this._super.apply(this, arguments);
        searchDomain.push(...this._getCategorySearchDomain());
        searchDomain.push(...this._getTagSearchDomain());
        searchDomain.push(...this._getBrandSearchDomain());   // 🔹 añadimos marcas

        const productNames = this.$el.get(0).dataset.productNames;
        if (productNames) {
            const nameDomain = [];
            for (const productName of productNames.split(',')) {
                if (!productName.length) {
                    continue;
                }
                if (nameDomain.length) {
                    nameDomain.unshift('|');
                }
                nameDomain.push(...[
                    '|', '|', ['name', 'ilike', productName],
                              ['default_code', '=', productName],
                              ['barcode', '=', productName],
                ]);
            }
            searchDomain.push(...nameDomain);
        }
        if (!this.el.dataset.showVariants) {
            searchDomain.push('hide_variants')
        }
        return searchDomain;
    },

    _getRpcParameters: function () {
        const productTemplateId = $("#product_details").find(".product_template_id");
        return Object.assign(this._super.apply(this, arguments), {
            productTemplateId: productTemplateId && productTemplateId.length ? productTemplateId[0].value : undefined,
        });
    },

    _getMainPageUrl() {
        return "/shop";
    },
});

const DynamicSnippetProductsCard = WebsiteSale.extend({
    selector: '.o_carousel_product_card',
    read_events: {
        'click .js_add_cart': '_onClickAddToCart',
        'click .js_remove': '_onRemoveFromRecentlyViewed',
    },

    init(root, options) {
        const parent = options.parent || root;
        this._super(parent, options);
    },

    start() {
        this.add2cartRerender = this.el.dataset.add2cartRerender === 'True';
    },

    async _onClickAddToCart(ev) {
        const button = ev.currentTarget
        if (!button.dataset.productSelected || button.dataset.isCombo === 'True') {
            const dummy_form = document.createElement('form');
            dummy_form.setAttribute('method', 'post');
            dummy_form.setAttribute('action', '/shop/cart/update');

            const inputPT = document.createElement('input');
            inputPT.setAttribute('name', 'product_template_id');
            inputPT.setAttribute('type', 'hidden');
            inputPT.setAttribute('value', button.dataset.productTemplateId);
            dummy_form.appendChild(inputPT);

            const inputPP = document.createElement('input');
            inputPP.setAttribute('name', 'product_id');
            inputPP.setAttribute('type', 'hidden');
            inputPP.setAttribute('value', button.dataset.productId);
            dummy_form.appendChild(inputPP);

            return this._handleAdd($(dummy_form));
        }
        else {
            const data = await rpc("/shop/cart/update_json", {
                product_id: parseInt(ev.currentTarget.dataset.productId),
                add_qty: 1,
                display: false,
            });
            wSaleUtils.updateCartNavBar(data);
            wSaleUtils.showCartNotification(this.call.bind(this), data.notification_info);
        }
        if (this.add2cartRerender) {
            this.trigger_up('widgets_start_request', {
                $target: this.$el.closest('.s_dynamic'),
            });
        }
    },

    async _onRemoveFromRecentlyViewed(ev) {
        const rpcParams = {}
        if (ev.currentTarget.dataset.productSelected) {
            rpcParams.product_id = ev.currentTarget.dataset.productId;
        } else {
            rpcParams.product_template_id = ev.currentTarget.dataset.productTemplateId;
        }
        await rpc("/shop/products/recently_viewed_delete", rpcParams);
        this.trigger_up('widgets_start_request', {
            $target: this.$el.closest('.s_dynamic'),
        });
    },
});

publicWidget.registry.dynamic_snippet_products_cta = DynamicSnippetProductsCard;
publicWidget.registry.dynamic_snippet_products = DynamicSnippetProducts;

export default DynamicSnippetProducts;


// /** @odoo-module **/

// import publicWidget from "@web/legacy/js/public/public_widget";
// import DynamicSnippetProducts from "website.snippets.s_dynamic_snippet_products.000";

// const DynamicSnippetProductsBrand = DynamicSnippetProducts.extend({

//     _getSearchDomain: function () {
//         const searchDomain = this._super.apply(this, arguments);
//         const el = this.$el.get(0);
//         const productBrandId = el && el.dataset ? el.dataset.productBrandId : null;

//         console.log(">>> _getSearchDomain brandId:", productBrandId);

//         if (productBrandId && productBrandId !== 'all') {
//             searchDomain.push(['dr_brand_value_id', '=', parseInt(productBrandId)]);
//         }

//         console.log(">>> searchDomain final:", searchDomain);
//         return searchDomain;
//     },

//     _getSearchContext: function () {
//         const searchContext = this._super.apply(this, arguments);
//         const el = this.$el.get(0);
//         const productBrandId = el && el.dataset ? el.dataset.productBrandId : null;

//         console.log(">>> _getSearchContext brandId:", productBrandId);

//         if (productBrandId && productBrandId !== 'all') {
//             searchContext.product_brand_id = parseInt(productBrandId);
//         }
//         return searchContext;
//     },
// });

// publicWidget.registry.dynamic_snippet_products = DynamicSnippetProductsBrand;

// export default DynamicSnippetProductsBrand;

