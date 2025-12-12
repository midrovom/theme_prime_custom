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
        'website_sale',
        'product',
        'droggol_theme_common',
    ],
    'data': [
        'data/brand_snippet_template_data.xml',

        'views/website_template.xml',

        'views/snippets/s_dynamic_snippet_brands.xml',
        'views/snippets/snippets.xml',
        'views/snippets/s_key_images_custom.xml',
        'views/templates_productos.xml',
        'views/snippets/s_text.xml',

        
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
            'conedera_theme_common/static/src/snippets/template_products/template_select.js',
            'conedera_theme_common/static/src/snippets/template_products/template_select.scss',

            'conedera_theme_common/static/src/snippets/s_dynamic_snippet_brand/snippet_brand.scss',
            'conedera_theme_common/static/src/snippets/s_dynamic_snippet_brand/000.js',

        ],
        'website.assets_wysiwyg': [
            'conedera_theme_common/static/src/snippets/s_dynamic_snippet_brand/option.js',
        ],
    }
}