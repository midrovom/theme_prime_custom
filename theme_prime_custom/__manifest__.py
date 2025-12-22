{
    'name': 'Theme Prime Custom',
    'version': '18.0.1.0.0',
    'summary': 'Temas y snippets personalizados para Conedera y Advance',
    'category': 'Theme/eCommerce',
    'depends': ['website', 'theme_prime', 'conedera_theme_common'],
    'data': [
        # Snippet Advance
        'views/advance/snippets_register_advance.xml',
        'views/advance/snippet/s_banner/s_banner_9_custom.xml',
        'views/advance/snippet/s_cover/s_cover_6.xml',
        'views/advance/snippet/s_shop_offer/s_shop_offer_6.xml',
        'views/advance/snippet/s_banner/s_banner_17.xml',
        'views/advance/snippet/s_shop_offer/s_shop_offer_7.xml',

    ],
    'assets': {
        'web.assets_frontend': [

    ],
        'website.assets_wysiwyg': [
        
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False
}
