# -*- coding: utf-8 -*-
{
    'name': 'Maintenance Report - Asignación a bodega',
    'summary': 'Devoluciones diferenciadas por empleado/departamento y trazabilidad permanente',
    'version': '18.0.1.17.0',
    'category': 'Maintenance',
    'license': 'LGPL-3',
    'depends': [
        'hr_maintenance',
        'maintenance_report',
        'maintenance_report_unifor',
    ],
    'data': [
        'security/ir.model.access.csv',
        'security/maintenance_bodega_history_rules.xml',
        'views/hr_employee_views.xml',
        'views/maintenance_equipment_views.xml',
        'views/maintenance_equipment_bodega_history_views.xml',
        'views/maintenance_equipment_list_views.xml',
        'data/maintenance_equipment_bodega_server_action.xml',
        'views/maintenance_report_wizard_views.xml',
        'report/maintenance_equipment_return_templates.xml',
        'report/maintenance_equipment_delivery_templates.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
