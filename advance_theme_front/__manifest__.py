{
    'name': 'Advance Theme Front',
    'version': '18.0.1.0.0',
    'description': 'Advance Theme Front',
    'summary': 'Advance Theme Front',
    'author': 'Mauricio Idrovo',
    'website': 'https://callphoneecuador.com',
    'license': 'LGPL-3',
    'category': 'Website/Website',
    'depends': [
        'website',
        'website_sale',
    ],
    'data': [
        'data/data.xml',
        'data/category_snippet_template_data.xml',
        'views/product_public_categ_view.xml',
        'views/snippets/s_dynamic_snippet_categories_preview_data.xml',
        'views/snippets/s_dynamic_snippet_category.xml',
        'views/snippets/snippets.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
    'assets': {
        'website.assets_wysiwyg': [
            'advance_theme_front/static/src/snippets/s_dynamic_snippet_categories/options.js',
        ],
    }
}