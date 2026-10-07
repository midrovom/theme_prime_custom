{
    "name": "HR Applications Portal Extension",
    "version": "18.0.1.0.7",
    "summary": "Portal para continuar y completar el Formulario 2 de postulaciones",
    "description": "Extiende custom_web_hr_datos_candidatos para separar el Formulario 2 y gestionar el historial de postulaciones del portal.",
    "author": "Callphone Ecuador / Bolivar Rodriguez",
    "license": "LGPL-3",
    "category": "Human Resources",
    "depends": ["custom_web_hr_datos_candidatos", "custom_web_candidatos", "portal", "website"],
    "data": [
        "security/ir.model.access.csv",
        "security/security.xml",
        "views/hr_applicant_views.xml",
        "views/portal_templates.xml",
        "views/application_form_2.xml"
    ],
    "assets": {
        "web.assets_frontend": [
            "hr_applications_portal_ext/static/src/js/application_form_2.js",
            "hr_applications_portal_ext/static/src/js/native_form_cleanup.js",
            "hr_applications_portal_ext/static/src/css/application_form_2.css"
        ]
    },
    "installable": True,
    "application": False,
    "auto_install": False
}