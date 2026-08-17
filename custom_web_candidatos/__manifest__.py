{
    'name': 'HR Recruitment WebSite Empleados Extencion',
    'version': '18.0.1.0.0',
    'description': '''
        Modulo desarrollado para la version community de Odoo 18
        Especificaciones del modulo:
        - Vista personalizada del formulario de datos para candidatos
    ''',
    'summary': 'Formulario de actualizacion de datos para candidatos',
    'author': 'Ing Bolivar Rodriguez',
    'website': 'https://callphoneecuador.ec',
    'license': 'LGPL-3',
    'category': 'Website',
    'depends': [
        'custom_web_hr_datos_candidatos','portal',
    ],
    'data': [
        'views/view_home.xml',

    ],
    'installable': True,
    'auto_install': False,
    'application': False,
    'assets': {
        "web.assets_frontend":[
        ]
        
    }
}