# -*- coding: utf-8 -*-
{
    'name': 'Maintenance Report - Bodega de devolucion',
    'summary': 'Reasigna el empleado del equipo al empleado vinculado al contacto bodega al devolverlo',
    'version': '18.0.1.2.0',
    'category': 'Maintenance',
    'license': 'LGPL-3',
    'depends': [
        'contacts',
        'hr_maintenance',
        'maintenance_report',
        'maintenance_report_unifor',
    ],
    'data': [
        'views/res_partner_views.xml',
        'views/maintenance_equipment_views.xml',
        'views/maintenance_report_wizard_views.xml',
        'report/maintenance_equipment_return_templates.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
