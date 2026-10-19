{
    "name": "Conedera Catastro - App de Campo",
    "summary": "PWA opcional de Catastro Comercial con acceso independiente y captura offline",
    "version": "18.0.1.3.0",
    "category": "Sales",
    "author": "Conedera",
    "license": "LGPL-3",
    "depends": [
        "conedera_odoo_census",
        "web",
        "sale_management",
        "sales_team",
    ],
    "data": [
        "security/mobile_security.xml",
        "security/ir.model.access.csv",
        "views/mobile_sync_views.xml",
        "views/mobile_app_menu.xml",
    ],
    "application": True,
    "installable": True,
}
