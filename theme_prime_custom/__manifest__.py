{
    'name': 'Theme Prime Custom',
    'version': '18.0.1.0.0',
    'summary': 'Temas y snippets personalizados para Conedera y Advance',
    'website': 'https://callphoneecuador.com',
    'license': 'LGPL-3',
    'category': 'Theme/eCommerce',
    'depends': ['website', 'theme_prime', 'webpage_theme_common'],
    'data': [

        #Snippet register
        'views/snippet_register.xml',

        # Snippet Advance
        'views/snippet/advance/s_banner/s_banner_16.xml',
        'views/snippet/advance/s_banner/s_banner_17.xml',
        'views/snippet/advance/s_cover/s_cover_6.xml',
        'views/snippet/advance/s_shop_offer/s_shop_offer_6.xml',
        'views/snippet/advance/s_shop_offer/s_shop_offer_7.xml',
        'views/snippet/advance/s_text/s_text.xml',

        'views/snippet/advance/s_footer/s_footer.xml',
        'views/snippet/advance/s_header/s_header.xml',

        #Snippet Conedera

        'views/snippet/conedera/s_cover_1/s_cover_1.xml',
        'views/snippet/conedera/s_dynamic_snippets/dynamic_snippets.xml',
        'views/snippet/conedera/s_banner_18/s_banner_18.xml',
        'views/snippet/conedera/product_detail_page.xml',

        'views/snippet/conedera/footers/footers.xml',
        'views/snippet/conedera/headers/headers.xml',

        'views/snippet/conedera/website_template.xml',

        # version mobil advance / conedera
        'views/header_mobil.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'theme_prime_custom/static/src/js/frontend/dynamic_snippets.js',
            'theme_prime_custom/static/src/xml/frontend/2_col_deal.xml',
        ],
        'website.assets_wysiwyg': [
            'theme_prime_custom/static/src/components/registries.js'
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
