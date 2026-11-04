# -*- coding: utf-8 -*-
{
    'name': 'Maintenance Report - Bodega de devolucion',
    'summary': 'Reasigna directamente el empleado del equipo al generar el acta de devolucion',
    'version': '18.0.1.3.0',
    'category': 'Maintenance',
    'license': 'LGPL-3',
    'depends': [
        'hr_maintenance',
        'maintenance_report',
        'maintenance_report_unifor',
    ],
    'data': [
        'views/maintenance_report_wizard_views.xml',
        'report/maintenance_equipment_return_templates.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
