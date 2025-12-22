{
    'name': 'Advance Theme Common',
    'version': '18.0.1.0.0',
    'summary': 'Extensión de estilos',
    'category': 'eCommerce',
    'depends': ['product','website', 'website_sale'],
    'data': [
        # 'data/data.xml',
        # 'data/category_snippet_template_data.xml',
        # 'data/product_snippet_template_data_custom.xml',

        # 'views/product_public_categ_view.xml',
        # 'views/snippets/s_dynamic_snippet_categories_preview_data.xml',
        # 'views/snippets/s_dynamic_snippet_category.xml',
        # 'views/snippets/snippets.xml',
        # 'views/product_attribute_view.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'advance_theme_common/static/src/scss/s_banner/s_banner_16.scss',
            'advance_theme_common/static/src/scss/s_banner/s_banner_17.scss',
            'advance_theme_common/static/src/scss/s_cover/s_cover_6.scss',
            # 'advance_theme_custom/static/src/scss/gallery_custom/gallery_custom.scss',
            # 'advance_theme_custom/static/src/scss/texto_custom/texto_custom.scss',
            # 'advance_theme_custom/static/src/scss/banner_custom/custom_category_slider.scss',
            # 'advance_theme_custom/static/src/scss/clients_custom/clients_custom.scss',
            # 'advance_theme_custom/static/src/scss/shop_offert_custom/s_shop_offer_custom.scss',
            # 'advance_theme_custom/static/src/scss/shop_offert_custom/s_shop_offer_hot.scss',
            # 'advance_theme_custom/static/src/scss/footer_custom/footer_custom.scss',
            # 'advance_theme_custom/static/src/scss/dynamic_custom/dynamic_custom.scss',
            # 'advance_theme_custom/static/src/scss/dynamic_custom/dynamic_filter_template_product_public_category_style_1.scss',
            # 'advance_theme_custom/static/src/snippets/dynamic_snippet_carousel_custom/dynamic_snippet_products_extend.js',
            # 'advance_theme_custom/static/src/scss/dynamic_custom/product_snippet_template_custom.scss',
            # 'advance_theme_custom/static/src/scss/product_item.scss',
    ],
        'website.assets_wysiwyg': [
            # 'advance_theme_custom/static/src/snippets/s_dynamic_snippet_categories/option.js',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False
}
