{
    'name': 'Conedera Theme Common',
    'version': '18.0.1.0.0',
    'description': '''
        Modulo desarrollado en odoo 18 community
        Personalizacion de estilos para theme_conedera
    ''',
    'summary': 'Estilos Theme Conedera',
    'author': 'Mauricio Idrovo',
    'website': 'https://callphoneecuador.com',
    'license': 'LGPL-3',
    'category': 'Website',
    'depends': [
        'website',
        'product',
        'website_sale',
        'droggol_theme_common',
    ],
    'data': [
        'data/data.xml',
        'data/brand_snippet_template_data.xml',

        'views/website_template.xml',

        #'views/snippets/s_dynamic_snippet_brands_preview_data.xml',
        'views/snippets/s_dynamic_snippet_brands.xml',
        'views/snippets/snippets.xml',
        'views/snippets/s_key_images_custom.xml',
        
    ],
    'auto_install': False,
    'application': False,
    'installable': True,
    'assets': {
        'web.assets_frontend': [
            'conedera_theme_common/static/src/scss/website.scss',
            'conedera_theme_common/static/src/snippets/s_banner_2/000.scss',
            'conedera_theme_common/static/src/css/style.css',
            'conedera_theme_common/static/src/snippets/footers/footer_style_11.scss',
            'conedera_theme_common/static/src/snippets/Key_images/key_images_custom.scss',

        ],
        'website.assets_wysiwyg': [
            'conedera_theme_common/static/src/snippets/s_dynamic_snippet_brand/option.js',
        ],
    }
}