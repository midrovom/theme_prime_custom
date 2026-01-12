{
    'name': 'webpage Theme Common',
    'version': '18.0.1.0.0',
    'summary': 'Extensión de estilos para Conedera / Advance',
    'category': 'eCommerce',
    'depends': ['product','website', 'website_sale'],
    'website': 'https://callphoneecuador.com',
    'license': 'LGPL-3',
    'data': [
        #Advance
        
        'data/advance/data.xml',
        'data/advance/category_snippet_template_data.xml',
        'data/advance/product_snippet_template_data_custom.xml',

        #Conedera
        'data/conedera/brand_snippet_template_data.xml',

        #Advance

        'views/snippets/advance/product_public_categ_view.xml',
        'views/snippets/advance/s_dynamic_categories/s_dynamic_snippet_categories_preview_data.xml',
        'views/snippets/advance/s_dynamic_categories/s_dynamic_snippet_category.xml',
        'views/snippets/advance/s_dynamic_categories/snippets.xml',

        #Conedera
        'views/snippets/conedera/website_template.xml',

        'views/snippets/conedera/s_dynamic_snippet_brand/s_dynamic_snippet_brands.xml',
        'views/snippets/conedera/s_key_images/snippets.xml',
        'views/snippets/conedera/s_key_images/s_key_images_custom.xml',
        
        'views/snippets/conedera/templates_productos.xml',

        #Advance/Conedera
        'views/product_attribute_view.xml',

    ],
    'assets': {
        'web.assets_frontend': [
            #Advance
            'webpage_theme_common/static/src/scss/advance/s_cover/s_cover_6_.scss',
            'webpage_theme_common/static/src/scss/advance/gallery_custom/gallery_custom.scss',
            'webpage_theme_common/static/src/scss/advance/s_text/s_text.scss',
            'webpage_theme_common/static/src/scss/advance/s_banner/s_banner_16.scss',
            'webpage_theme_common/static/src/scss/advance/s_banner/s_banner_17.scss',

            'webpage_theme_common/static/src/scss/advance/s_shop_offert/s_shop_offer_6.scss',
            'webpage_theme_common/static/src/scss/advance/s_shop_offert/shop_offert_7.scss',
            'webpage_theme_common/static/src/scss/advance/s_footer/s_footer.scss',

            'webpage_theme_common/static/src/scss/advance/dynamic_custom/dynamic_custom.scss',

            'webpage_theme_common/static/src/scss/advance/dynamic_custom/dynamic_filter_template_product_public_category_style_1.scss',
            
            'webpage_theme_common/static/src/scss/advance/dynamic_custom/product_snippet_template_custom.scss',
            'webpage_theme_common/static/src/scss/advance/product_item.scss',

            #Conedera

            'webpage_theme_common/static/src/scss/conedera/website.scss',
            'webpage_theme_common/static/src/scss/conedera/snippets/s_banner_2/000.scss',
            'webpage_theme_common/static/src/css/conedera/style.css',

            'webpage_theme_common/static/src/scss/conedera/snippets/footers/footer_style_12.scss',
            'webpage_theme_common/static/src/scss/conedera/snippets/headers/prime_style_9.scss',

            'webpage_theme_common/static/src/scss/conedera/snippets/Key_images/key_images_custom.scss',
            'webpage_theme_common/static/src/scss/conedera/snippets/template_products/template_select.scss',
            'webpage_theme_common/static/src/scss/conedera/snippets/template_products/image_product.scss',
            'webpage_theme_common/static/src/scss/conedera/snippets/s_dynamic_style_12_theme_prime/s_style_12.scss',

            'webpage_theme_common/static/src/scss/conedera/snippets/s_dynamic_snippet_brand/snippet_brand.scss',

            #Advance/Conedera (Dynamic_snippet)

            'webpage_theme_common/static/src/scss/conedera/snippets/header_mobile_custom/header_mobile.scss',
            'webpage_theme_common/static/src/snippet/dynamic_snippet_custom/dynamic_snippet_custom.js',
    ],
        'website.assets_wysiwyg': [
            'webpage_theme_common/static/src/scss/advance/snippets/s_dynamic_snippet_categories/option.js',
            'webpage_theme_common/static/src/scss/conedera/snippets/s_dynamic_snippet_brand/option.js',
            'webpage_theme_common/static/src/snippet/dynamic_snippet_custom/dynamic_snippet_option_custom.js',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False
}
