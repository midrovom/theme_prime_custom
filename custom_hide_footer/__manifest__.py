{
    'name': 'custom_hide_footer',
    'version': '16.0.1.0.0',
    'category': 'website',
    'summary': 'Modulo para ocultar footers',
    'website': 'https://callphoneecuador.com',
    'license': 'LGPL-3',
    'description': """
        Este módulo permite generar Acta de entrega de equipos.
    """,
    'author': 'Ing. Bolivar Rodriguez',
    'depends': ['website','website_sale'],
    'data': [
        # 'views/assets.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'custom_hide_footer/static/src/css/hide_footer.css'
        ],
    },

    'installable': True,
    'application': False,
    'auto_install': False,

 }