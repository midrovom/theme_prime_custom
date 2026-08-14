{
    "name": "Solicitudes de Desarrollo ERP",
    "version": "18.0.1.0.0",
    "category": "Services/Project",
    "summary": "Gestión y control de desarrollos y cambios solicitados a Sistemas",
    "author": "Conedera S.A.",
    "license": "LGPL-3",
    "depends": ["base", "mail"],
    "data": [
        "security/erp_change_request_security.xml",
        "security/ir.model.access.csv",
        "data/erp_request_sequence.xml",
        "views/erp_request_department_views.xml",
        "views/erp_change_request_views.xml",
        "views/erp_change_request_menus.xml",
    ],
    "application": True,
    "installable": True,
}

