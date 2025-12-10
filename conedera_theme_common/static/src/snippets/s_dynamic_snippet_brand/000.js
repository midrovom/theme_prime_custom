/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";
import { rpc } from "@web/core/network/rpc";
import DynamicSnippetCarousel from "@website/snippets/s_dynamic_snippet_carousel/000";
import wSaleUtils from "@website_sale/js/website_sale_utils";
import { WebsiteSale } from "../../js/website_sale";

const DynamicSnippetProductsBrand = DynamicSnippetCarousel.extend({
    selector: '.s_dynamic_snippet_products',

    //--------------------------------------------------------------------------
    // Private
    //--------------------------------------------------------------------------

    /**
     * Gets the brand search domain
     *
     * @private
     */
    _getBrandSearchDomain() {
        const searchDomain = [];
        let productBrandId = this.$el.get(0).dataset.productBrandId;
        if (productBrandId && productBrandId !== 'all') {
            if (productBrandId === 'current') {
                productBrandId = undefined;
                const productBrandField = $("#product_details").find(".product_brand_id");
                if (productBrandField && productBrandField.length) {
                    productBrandId = parseInt(productBrandField[0].value);
                }
                if (!productBrandId) {
                    this.trigger_up('main_object_request', {
                        callback: function (value) {
                            if (value.model === "product.attribute.value") {
                                productBrandId = value.id;
                            }
                        },
                    });
                }
                if (!productBrandId) {
                    const productTemplateId = $("#product_details").find(".product_template_id");
                    if (productTemplateId && productTemplateId.length) {
                        searchDomain.push(['value_ids.product_tmpl_id', '=', parseInt(productTemplateId[0].value)]);
                    }
                }
            }
            if (productBrandId) {
                // usamos el campo estándar value_ids de product.template
                searchDomain.push(['value_ids', '=', parseInt(productBrandId)]);
            }
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
        searchDomain.push(...this._getBrandSearchDomain());
        return searchDomain;
    },

    /**
     * Add `productTemplateId` for product snippets (Accessories, Alternatives and Recently sold).
     *
     * @override
     * @private
     */
    _getRpcParameters: function () {
        const productTemplateId = $("#product_details").find(".product_template_id");
        return Object.assign(this._super.apply(this, arguments), {
            productTemplateId: productTemplateId && productTemplateId.length ? productTemplateId[0].value : undefined,
        });
    },

    /**
     * @override
     * @private
     */
    _getMainPageUrl() {
        return "/shop";
    },
});

const DynamicSnippetProductsCardBrand = WebsiteSale.extend({
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

    //--------------------------------------------------------------------------
    // Handlers
    //--------------------------------------------------------------------------

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

publicWidget.registry.dynamic_snippet_products_cta = DynamicSnippetProductsCardBrand;
publicWidget.registry.dynamic_snippet_products = DynamicSnippetProductsBrand;

export default DynamicSnippetProductsBrand;
