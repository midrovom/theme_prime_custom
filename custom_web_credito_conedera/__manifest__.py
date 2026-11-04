{
    'name': 'Portal de Solicitudes de Crédito CONEDERA',
    'version': '18.0.1.8.51',
    'summary': 'Registro verificado, solicitudes de crédito, etapas e ingreso documental para CONEDERA S.A.',
    'description': '''
Portal de solicitudes de crédito CONEDERA S.A. para Odoo 18.
- Registro nativo de Odoo con aceptación de términos y condiciones del módulo custom_web_hr_datos_candidatos y verificación de correo mediante OTP en modal.
- Formulario web basado en la Solicitud de Crédito CONEDERA proporcionada.
- Campo applicant_name (Many2one a res.partner), con migración segura del nombre histórico y selección de clientes desde el backend.
- Historial del solicitante y línea de tiempo de etapas.
- Flujo kanban interno de gestión.
- Ingreso de documentos habilitado al aprobar la solicitud y con documentos configurables por tipo de solicitante.
- Ubicación y croquis integrados como paso 3 de seis; expedientes y PDF de ubicación permanecen independientes del PDF de solicitud.
''',
    'author': 'OpenAI',
    'license': 'LGPL-3',
    'category': 'Website',
    'depends': ['base', 'mail', 'portal', 'website', 'web', 'auth_signup', 'custom_web_hr_datos_candidatos'],
    'data': [
        'security/credit_security.xml',
        'security/ir.model.access.csv',
        'data/credit_sequence.xml',
        'data/credit_catalog_sequences.xml',
        'data/credit_stages.xml',
        'data/credit_applicant_types.xml',
        'data/credit_marital_statuses.xml',
        'data/credit_housing_types.xml',
        'data/credit_verification_catalogs.xml',
        'data/credit_bank_account_types.xml',
        'data/credit_employer_types.xml',
        'data/website_menu.xml',
        'views/credit_stage_views.xml',
        'views/credit_application_views.xml',
        'views/res_partner_credit_views.xml',
        'views/credit_print_wizard_views.xml',
        'reports/credit_application_report.xml',
        'views/credit_access_wizard_views.xml',
        'views/credit_theme_views.xml',
        'views/res_users_credit_views.xml',
        'views/credit_applicant_type_views.xml',
        'views/credit_marital_status_views.xml',
        'views/credit_housing_type_views.xml',
        'views/credit_verification_catalog_views.xml',
        'views/credit_reference_policy_views.xml',
        'views/credit_bank_account_type_views.xml',
        'views/credit_employer_type_views.xml',
        'views/credit_documents_views.xml',
        'views/ir_mail_server_view.xml',
        'views/portal_templates.xml',
        'views/website_credit_login_views.xml',
        'data/credit_upgrade.xml',
    ],
    'assets': {
        'web.report_assets_common': [
            'custom_web_credito_conedera/static/src/css/credit_application_report.css',
        ],
        'web.assets_backend': [
            'custom_web_credito_conedera/static/src/css/credit_backend_verification.css',
            'custom_web_credito_conedera/static/src/css/credit_signed_dropzone.css',
            'custom_web_credito_conedera/static/src/js/credit_signed_dropzone.js',
        ],
        'web.assets_frontend': [
            'custom_web_credito_conedera/static/src/css/credit_portal.css',
            'custom_web_credito_conedera/static/src/css/credit_pwa.css',
            'custom_web_credito_conedera/static/src/css/credit_offline.css',
            'custom_web_credito_conedera/static/src/js/credit_pwa.js',
            'custom_web_credito_conedera/static/src/js/credit_portal.js',
            'custom_web_credito_conedera/static/src/js/credit_offline.js',
            'custom_web_credito_conedera/static/src/js/credit_offline_operations.js',
        ],
    },
    'installable': True,
    'auto_install': False,
    'application': True,
}
