{
    "name": "HR Recruitment EC Contract - Filtro por Fecha",
    "version": "18.0.1.0.0",
    "category": "Human Resources/Recruitment",
    "summary": "Filtro por fecha para paquetes de contratación",
    "author": "Ing. Bolivar Rodriguez",
    "license": "LGPL-3",
    "depends": [
        "hr_recruitment_ec_contract",
        "web",
    ],
    "data": [
        'views/filter.xml',
    ],
    "assets": {
        "web.assets_backend": [
            "hr_recruitment_ec_contract_date_filter/static/src/js/onboarding_package_date_filter.js",
            "hr_recruitment_ec_contract_date_filter/static/src/xml/onboarding_package_date_filter.xml",
            'hr_recruitment_ec_contract_date_filter/static/src/css/date_filter.css',
        ],
    },
    "installable": True,
    "application": False,
}