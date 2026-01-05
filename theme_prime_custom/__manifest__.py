{
    'name': 'Theme Prime Custom',
    'version': '18.0.1.0.0',
    'summary': 'Temas y snippets personalizados para Conedera y Advance',
    'category': 'Theme/eCommerce',
    'depends': ['website', 'theme_prime', 'conedera_theme_common'],
    'data': [
        # Snippet Advance
        # 'views/advance/snippets_register_advance.xml',
        # 'views/advance/snippet/s_banner/s_banner_9_custom.xml',
        # 'views/advance/snippet/s_cover/s_cover_6.xml',
        # 'views/advance/snippet/s_shop_offer/s_shop_offer_6.xml',
        # 'views/advance/snippet/s_banner/s_banner_17.xml',
        # 'views/advance/snippet/s_shop_offer/s_shop_offer_7.xml',
        # 'views/advance/snippet/s_text/s_text.xml',
        # 'views/advance/snippet/s_footer/s_footer.xml',
        # 'views/advance/snippet/s_header/s_header.xml',

        #Snippet Conedera
        'views/conedera/snippet/s_footer/footers.xml',
        'views/conedera/snippet/s_cover/s_cover_1.xml',
        'views/conedera/snippet/s_d_2_column/dynamic_snippets.xml',
        'views/conedera/product_detail_page.xml',
        'views/conedera/snippet/s_banner/s_banner_16.xml',
        'views/conedera/snippets_register_conedera.xml',
        'views/conedera/snippet/s_header/headers.xml',
        'views/conedera/website_template.xml',

    ],
    'assets': {
        'web.assets_frontend': [
            'theme_prime_custom/static/src/js/frontend/dynamic_snippets.js',
            'theme_prime_custom/static/src/xml/frontend/2_col_deal.xml',

    ],
        'website.assets_wysiwyg': [
            'theme_prime_custom/static/src/components/registries.js',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False
}
