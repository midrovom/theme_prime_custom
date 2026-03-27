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
    'depends': ['base','maintenance', 'hr'],
    'data': [
        'security/ir.model.access.csv',
        'report/maintenance_report.xml',
        'report/maintenance_report_templates.xml',
        'report/maintenance_equipment_return.xml',
        'views/hr_views.xml',
        'views/hr_department_views.xml',
        # 'views/hr_footer_views.xml',
        'views/res_company_view.xml',
    ],
    'assets': {
        'web.assets_frontend': [

        ],
    },

    'installable': True,
    'application': False,
    'auto_install': False,

 }