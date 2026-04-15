{
    'name': 'HR Recruitment WebSite Empleados',
    'version': '18.0.1.0.0',
    'description': '''
        Modulo desarrollado para la version community de Odoo 18
        Especificaciones del modulo:
        - Vista personalizada del formulario de datos para candidatos
    ''',
    'summary': 'Formulario de actualizacion de datos para candidatos',
    'author': 'Ing.Mauricio Idrovo, Ing Bolivar Rodriguez',
    'website': 'https://callphoneecuador.ec',
    'license': 'LGPL-3',
    'category': 'Website',
    'depends': [
        'base',
        'contacts',
        'hr_recruitment',
        'web',
        'website',
        'auth_signup', 
        'portal', 
        'mail',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/website_menu.xml',
        'data/mail_template.xml',

        'report/applicant_report_action.xml',
        'report/report_view.xml',

        'views/hr_applicant_views.xml',
        'views/views_form/recruitment_form_1.xml',
        'views/views_form/recruitment_form_2.xml',
        'views/views_form/recruitment_form_3.xml',
        'views/views_form/website_hr_recruitment.xml',
        'views/error_template/error_templates.xml',
        'views/footer/hr_footer_views.xml',
        'views/signup/signup_templates.xml',
        'views/footer/hr_reglamento_interno.xml',
        'views/ir_mail_server_view.xml',

    ],
    'installable': True,
    'auto_install': False,
    'application': False,
    'assets': {
        "web.assets_frontend":[
            "custom_web_hr_datos_candidatos/static/src/css/styles.css",
            "custom_web_hr_datos_candidatos/static/src/js/website_hr_recruitment.js",
        ]
        
    }
}