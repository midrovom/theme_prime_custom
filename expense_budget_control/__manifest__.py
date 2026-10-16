# -*- coding: utf-8 -*-
{
    'name': 'Control de Presupuesto de Gastos',
    'summary': 'Presupuesto mensual por rubro y cuenta, Excel y sincronización API',
    'version': '18.0.1.4.50',
    'category': 'Accounting/Accounting',
    'author': 'Conedera Desarrollo',
    'license': 'LGPL-3',
    'depends': ['base', 'web', 'api_administrator'],
    'external_dependencies': {'python': ['openpyxl']},
    'data': [
        'security/expense_budget_security.xml',
        'security/ir.model.access.csv',
        'data/comparison_months.xml',
        'views/expense_budget_comparison_report_wizard_views.xml',
        'views/expense_budget_views.xml',
        'views/expense_budget_import_views.xml',
        'views/expense_budget_api_views.xml',
        'views/expense_budget_dashboard_views.xml',
        'views/expense_budget_menus.xml',
        'report/annual_budget_report.xml',
        'report/comparison_report.xml',
        'data/expense_budget_cron.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'expense_budget_control/static/src/dashboard/dashboard.js',
            'expense_budget_control/static/src/dashboard/dashboard.xml',
            'expense_budget_control/static/src/dashboard/dashboard.scss',
        ],
    },
    'application': True,
    'installable': True,
}
