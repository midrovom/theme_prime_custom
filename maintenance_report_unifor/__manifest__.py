{
    'name': 'Maintenance Report Unifor',
    'version': '18.0.1.0.0',
    'category': 'Maintenance',
    'summary': 'Reporte PDF para Acta de Entrega de Uniforme',
    'website': 'https://callphoneecuador.com',
    'license': 'LGPL-3',
    'description': """
        Este módulo permite generar Acta de entrega de uniforme.
    """,
    'author': 'Ing. Bolivar Rodriguez',
    'depends': ['maintenance_report'],
    'data': [
        'report/maintenance_report_views.xml',
        'report/maintenance_report_templates.xml',
        'views/maintenance_report_views.xml',
    ],
    'assets': {
        'web.assets_frontend': [

        ],
    },

    'installable': True,
    'application': False,
    'auto_install': False,

 }