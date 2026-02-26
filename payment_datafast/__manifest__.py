{
    'name': 'DataFast Payment',
    'version': '18.0.1.0.0',
    'description': '''
        Modulo desarrollado en Odoo 16 Community
        Especificaciones:
            - Integración de pasarela de pagos DataFast
            - Botón de pagos en el sitio web
    ''',
    'summary': 'Botón de Pagos DataFast',
    'author': 'Mauricio Idrovo',
    'website': 'www.callphoneecuador.com',
    'license': 'LGPL-3',
    'category': 'Accounting/Payment Providers',
    'description': " ",
    'sequence': 350,
    'depends': [
        'web',
        'payment',
        'website',
        'website_sale',
        'account',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/payment_datafast_templates.xml',
        'views/payment_provider_views.xml',
        'views/payment_transaction_views.xml',
        'views/res_partner_views.xml',
        'wizard/transaction_verified.xml',

        'data/payment_provider_data.xml', 
    ],
    'assets': {
        'web.assets_frontend': [
            'payment_datafast/static/src/js/payment_form.js',
            'payment_datafast/static/src/js/wpwl_options.js',
            'payment_datafast/static/src/css/style_datafast.css',
        ],
    },
    'application': False,
    'installable': True,
    'post_init_hook': 'post_init_hook',
    'uninstall_hook': 'uninstall_hook',
    'license': 'LGPL-3',
}