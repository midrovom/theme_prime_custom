/** @odoo-module **/

import options from "@web_editor/js/editor/snippets.options";
import s_dynamic_snippet_carousel_options from "@website/snippets/s_dynamic_snippet_carousel/options";
import wUtils from "@website/js/utils";

const alternativeSnippetRemovedOptions = [
    'filter_opt', 'product_category_opt', 'product_tag_opt', 'product_names_opt',
];

const dynamicSnippetProductsOptions = s_dynamic_snippet_carousel_options.extend({

    init() {
        this._super.apply(this, arguments);

        this.modelNameFilter = 'product.product';
        this.productBrands = {};
        this.productCategories = {};

        this.orm = this.bindService("orm");

        this.isAlternativeProductSnippet =
            this.$target.hasClass("o_wsale_alternative_products");
    },

    _computeWidgetVisibility(widgetName, params) {
        if (this.isAlternativeProductSnippet && alternativeSnippetRemovedOptions.includes(widgetName)) {
            return false;
        }
        return this._super(...arguments);
    },

    //----------------------------------------------------------------------
    // Fetchers
    //----------------------------------------------------------------------

    _fetchProductBrands: async function () {
        const brandAttr = await this.orm.searchRead(
            "product.attribute",
            [["name", "=", "Brand"]],
            ["id"]
        );

        if (!brandAttr.length) {
            return [];
        }

        return this.orm.searchRead(
            "product.attribute.value",
            [["attribute_id", "=", brandAttr[0].id]],
            ["id", "name"]
        );
    },

    _fetchProductCategories() {
        return this.orm.searchRead(
            "product.public.category",
            wUtils.websiteDomain(this),
            ["id", "name"]
        );
    },

    //----------------------------------------------------------------------
    // Render
    //----------------------------------------------------------------------

    async _renderCustomXML(uiFragment) {
        await this._super(...arguments);
        await this._renderProductCategorySelector(uiFragment);
        await this._renderProductBrandSelector(uiFragment);
    },

    async _renderProductBrandSelector(uiFragment) {
        const brands = await this._fetchProductBrands();
        for (let b of brands) {
            this.productBrands[b.id] = b;
        }
        const brandSelector = uiFragment.querySelector('[data-name="product_brand_opt"]');
        return this._renderSelectUserValueWidgetButtons(brandSelector, this.productBrands);
    },

    async _renderProductCategorySelector(uiFragment) {
        const categories = await this._fetchProductCategories();
        for (let c of categories) {
            this.productCategories[c.id] = c;
        }
        const categorySelector = uiFragment.querySelector('[data-name="product_category_opt"]');
        return this._renderSelectUserValueWidgetButtons(categorySelector, this.productCategories);
    },

    _setOptionsDefaultValues() {
        this._setOptionValue("productBrandId", "all");
        this._setOptionValue("productCategoryId", "all");
        this._setOptionValue("showVariants", true);
        this._super(...arguments);
    },
});

options.registry.dynamic_snippet_products = dynamicSnippetProductsOptions;
export default dynamicSnippetProductsOptions;


// /** @odoo-module **/

// import options from "@web_editor/js/editor/snippets.options";
// import s_dynamic_snippet_carousel_options from "@website/snippets/s_dynamic_snippet_carousel/options";
// import wUtils from "@website/js/utils";

// const alternativeSnippetRemovedOptions = [
//     'filter_opt', 'product_category_opt', 'product_tag_opt', 'product_names_opt',
// ]

// const dynamicSnippetProductsOptions = s_dynamic_snippet_carousel_options.extend({

//     init: function () {
//         this._super.apply(this, arguments);
//         this.modelNameFilter = 'product.product';

//         const productTemplateId = this.$target.closest("#wrapwrap").find("input.product_template_id");
//         this.hasProductTemplateId = productTemplateId.val();
//         if (!this.hasProductTemplateId) {
//             this.contextualFilterDomain.push(['product_cross_selling', '=', false]);
//         }

//         this.productCategories = {};
//         this.productBrands = {};   // 🔹 nuevo diccionario para marcas
//         this.isAlternativeProductSnippet = this.$target.hasClass('o_wsale_alternative_products');

//         this.orm = this.bindService("orm");
//     },

//     _computeWidgetVisibility(widgetName, params) {
//         if (this.isAlternativeProductSnippet && alternativeSnippetRemovedOptions.includes(widgetName)) {
//             return false;
//         }
//         return this._super(...arguments);
//     },

//     //--------------------------------------------------------------------------
//     // Fetchers
//     //--------------------------------------------------------------------------

//     _fetchProductCategories: function () {
//         return this.orm.searchRead("product.public.category", wUtils.websiteDomain(this), ["id", "name"]);
//     },

//     /**
//      * 🔹 Nuevo: Fetches product brands desde product.attribute.value
//      */
//     _fetchProductBrands: async function () {
//         // Busca el atributo "Marca"
//         const brandAttribute = await this.orm.searchRead(
//             "product.attribute",
//             [["name", "=", "Marca"]],
//             ["id"]
//         );
//         if (!brandAttribute.length) {
//             return [];
//         }
//         const brandAttributeId = brandAttribute[0].id;

//         // Trae los valores de ese atributo
//         return this.orm.searchRead(
//             "product.attribute.value",
//             [["attribute_id", "=", brandAttributeId]],
//             ["id", "name"]
//         );
//     },

//     //--------------------------------------------------------------------------
//     // Renderers
//     //--------------------------------------------------------------------------

//     async _renderCustomXML(uiFragment) {
//         await this._super.apply(this, arguments);
//         await this._renderProductCategorySelector(uiFragment);
//         await this._renderProductBrandSelector(uiFragment);   
//     },

//     _renderProductCategorySelector: async function (uiFragment) {
//         const productCategories = await this._fetchProductCategories();
//         for (let index in productCategories) {
//             this.productCategories[productCategories[index].id] = productCategories[index];
//         }
//         const productCategoriesSelectorEl = uiFragment.querySelector('[data-name="product_category_opt"]');
//         return this._renderSelectUserValueWidgetButtons(productCategoriesSelectorEl, this.productCategories);
//     },

//     /**
//      * 🔹 Nuevo: Renderiza las marcas en el builder
//      */
//     _renderProductBrandSelector: async function (uiFragment) {
//         const productBrands = await this._fetchProductBrands();
//         for (let index in productBrands) {
//             this.productBrands[productBrands[index].id] = productBrands[index];
//         }
//         const productBrandsSelectorEl = uiFragment.querySelector('[data-name="product_brand_opt"]');
//         return this._renderSelectUserValueWidgetButtons(productBrandsSelectorEl, this.productBrands);
//     },

//     _setOptionsDefaultValues: function () {
//         this._setOptionValue('productCategoryId', 'all');
//         this._setOptionValue('productBrandId', 'all');   
//         this._setOptionValue('showVariants', true);
//         this._super.apply(this, arguments);
//     },
// });

// options.registry.dynamic_snippet_products = dynamicSnippetProductsOptions;

// export default dynamicSnippetProductsOptions;
