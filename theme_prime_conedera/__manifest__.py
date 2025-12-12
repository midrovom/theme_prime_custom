{
    'name': 'Theme Prime Conedera',
    'version': '18.0.1.0.0',
    'description': '''
        Modulo personalizado para Odoo 18 CM
        Personalizacion de temas y snippets para la página de Conedera
    ''',
    'summary': 'Temas y snippets personalizados para Conedera',
    'author': 'Ing. Mauricio Idrovo',
    'website': 'https://callphoneecuador.com',
    'license': 'LGPL-3',
    'category': 'Theme/eCommerce',
    'images': [
        'static/description/screenshot-2.png',
    ],
    'depends': [
        'website',
        'theme_prime',
        'conedera_theme_common'
    ],
    'data': [
        'views/headers.xml',
        'views/footers.xml',
        'views/snippets/s_cover_1.xml',
        'views/snippets/dynamic_snippets.xml',
        'views/snippets.xml',
        'views/snippets/s_banner_16.xml',
        'views/snippets/s_info_block.xml',
    ],
    'auto_install': False,
    'application': False,
    'installable': True,
    'assets': {
        'web.assets_frontend': [
            'theme_prime_conedera/static/src/js/frontend/dynamic_snippets.js',
            # 'theme_prime_conedera/static/src/xml/frontend/s_image_products.xml',
            'theme_prime_conedera/static/src/xml/frontend/2_col_deal.xml',
        ],
        'website.assets_wysiwyg': [
            'theme_prime_conedera/static/src/components/registries.js'
        ],
        
    },
}