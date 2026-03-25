{
    'name': 'Maintenance Report',
    'version': '18.0.1.0.0',
    'category': 'Maintenance',
    'summary': 'Reporte PDF para Acta de Entrega de Equipos',
    'website': 'https://callphoneecuador.com',
    'license': 'LGPL-3',
    'description': """
        Este módulo permite generar Acta de entrega de equipos.
    """,
    'author': 'Ing. Bolivar Rodriguez',
    'depends': ['maintenance'],
    'data': [
        'reports/maintenance_report.xml',
        'views/maintenance_report_templates.xml',
    ],
    'assets': {
        'web.assets_frontend': [

        ],
    },

    'installable': True,
    'application': False,
    'auto_install': False,

 }