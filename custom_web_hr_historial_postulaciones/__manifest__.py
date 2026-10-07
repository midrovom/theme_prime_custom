{
    'name': 'Portal - Historial de Postulaciones',
    'version': '18.0.1.0.0',
    'summary': 'Historial de postulaciones, actualización de datos e ingreso de documentación',
    'description': '''
        Extensión del módulo custom_web_hr_datos_candidatos para el portal.

        Funcionalidades:
        - Historial de postulaciones del usuario portal.
        - Habilitación controlada para actualizar los datos de una postulación.
        - Reutilización del formulario nativo de reclutamiento para la actualización.
        - Activación del ingreso de documentación a partir de la etapa de secuencia 3.
        - Modelo de documentación obligatoria relacionado con hr.applicant.
        - Validación servidor/portal de todos los documentos obligatorios.
    ''',
    'author': 'OpenAI',
    'license': 'LGPL-3',
    'category': 'Website',
    'depends': [
        'custom_web_hr_datos_candidatos',
        'portal',
        'website',
        'hr_recruitment',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/hr_applicant_views.xml',
        'views/portal_home.xml',
        'views/portal_application_history.xml',
        'views/portal_application_edit.xml',
        'views/portal_documentation.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'custom_web_hr_historial_postulaciones/static/src/js/application_edit.js',
            'custom_web_hr_historial_postulaciones/static/src/css/portal_applications.css',
        ],
    },
    'installable': True,
    'auto_install': False,
    'application': False,
}
