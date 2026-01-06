{
    'name': 'webpage Theme Common',
    'version': '18.0.1.0.0',
    'summary': 'Extensión de estilos para Conedera / Advance',
    'category': 'eCommerce',
    'depends': ['product','website', 'website_sale'],
    'data': [
        #Advance
        'data/advance/data.xml',
        'data/advance/category_snippet_template_data.xml',
        'data/advance/product_snippet_template_data_custom.xml',

        #Conedera
        # 'data/conedera/brand_snippet_template_data.xml',

        #Advance
        'views/advance/product_public_categ_view.xml',
        'views/advance/snippets/s_dynamic_categories/s_dynamic_snippet_categories_preview_data.xml',
        'views/advance/snippets/s_dynamic_categories/s_dynamic_snippet_category.xml',
        'views/advance/snippets/s_dynamic_categories/snippets.xml',
        'views/advance/snippets/s_dynamic_categories/snippets.xml',
        'views/advance/product_attribute_view.xml',

    ],
    'assets': {
        'web.assets_frontend': [
            #Advance
            'webpage_theme_common/src/advance/scss/s_cover/s_cover_6.scss',
            'webpage_theme_common/src/advance/scss/gallery_custom/gallery_custom.scss',
            'webpage_theme_common/src/advance/scss/s_text/s_text.scss',
            'webpage_theme_common/src/advance/scss/s_banner/s_banner_16.scss',
            'webpage_theme_common/src/advance/scss/s_banner/s_banner_17.scss',
            'webpage_theme_common/src/advance/scss/s_footer/s_footer.scss',
            'webpage_theme_common/src/advance/scss/s_shop_offert/s_shop_offer_6.scss',
            'webpage_theme_common/src/advance/scss/s_shop_offert/shop_offert_7.scss',
            'webpage_theme_common/src/advance/scss/dynamic_custom/dynamic_filter_template_product_public_category_style_1.scss',
            'webpage_theme_common/src/advance/scss/dynamic_custom/product_snippet_template_custom.scss',
            'webpage_theme_common/src/advance/snippets/dynamic_snippet_carousel_custom/dynamic_snippet_products_extend.js',
            'webpage_theme_common/src/advance/scss/product_item.scss',
    ],
        'website.assets_wysiwyg': [
            'webpage_theme_common/src/advance/snippets/s_dynamic_snippet_categories/option.js',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False
}
