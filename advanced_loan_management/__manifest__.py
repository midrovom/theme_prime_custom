# -*- coding: utf-8 -*-
################################################################################
#
#    Cybrosys Technologies Pvt. Ltd.
#
#    Copyright (C) 2023-TODAY Cybrosys Technologies(<https://www.cybrosys.com>).
#    Author: Sabeel B (odoo@cybrosys.com)
#
#    You can modify it under the terms of the GNU AFFERO
#    GENERAL PUBLIC LICENSE (AGPL v3), Version 3.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU AFFERO GENERAL PUBLIC LICENSE (AGPL v3) for more details.
#
#    You should have received a copy of the GNU AFFERO GENERAL PUBLIC LICENSE
#    (AGPL v3) along with this program.
#    If not, see <http://www.gnu.org/licenses/>.
#
################################################################################
{
    'name': 'Financing plan',
    'version': '18.0.1.0.0',
    'summary':  'Le ayuda a gestionar solicitudes/desembolsos de préstamos/'
                'Operaciones de amortización/amortización',
    'description':  'Módulo Permite Crear diferentes tipos de préstamos,'
                    'Gestione las solicitudes de préstamos y las operaciones de amortización de forma sencilla'
                    'Crear facturas para cada monto de reembolso',
    'category': 'Accounting',
    'author': "Callphone",
    'website': "https://www.callphone.com.ec",
    'images': ['static/description/banner.png'],
    'company': "Callphone",
    'depends': ['mail', 'account', 'base','product'],
    'demo': ['data/loan_journal_data.xml'],
    'data': [
        'security/loan_management_groups.xml',
        'security/loan_management_security.xml',
        'security/ir.model.access.csv',
        'views/loan_type_views.xml',
        'views/loan_request_views.xml',
        'views/repayment_lines_views.xml',
        'views/loan_documents_views.xml',
        'views/res_config_settings_views.xml',
        'views/loan_management_menus.xml',
        'views/res_partner_views.xml',
        'wizard/message_popup_views.xml',
        'wizard/reject_reason_views.xml',
        'report/loan_management_reports.xml',
        'report/loan_report_templates.xml',
        'data/cron.xml',
    ],

    'license': 'AGPL-3',
    'installable': True,
    'auto_install': False,
    'application': True,
}
