{
    "name": "Recruitment EC - Contratos y Décimos Extencion",
    "summary": "Bloqua campos para que usuarios determinados no puedan modificar finalizado el proceso",
    "version": "18.0.1.1.0",
    "category": "Human Resources/Recruitment",
    "author": "Custom Development",
    "license": "LGPL-3",
    "depends": [
        "hr_recruitment_ec_contract",
    ],
    "data": [
        "views/hr_applicant_view.xml",
    ],
    "assets": {
        "web.assets_backend": [
            # "hr_recruitment_ec_contract/static/src/js/document_variable_drag.js",
            # "hr_recruitment_ec_contract/static/src/xml/document_variable_drag.xml",
        ],
    },
    "application": True,
    "installable": True,
    "auto_install": False,
}
