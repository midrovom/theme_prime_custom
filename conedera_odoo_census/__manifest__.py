{
    "name": "Conedera - Catastro Comercial (Community)",
    "version": "18.0.1.1.0",
    "category": "Sales/Sales",
    "summary": "Catastro móvil de clientes, visitas comerciales, GPS y proformas",
    "description": """
Catastro comercial para Odoo 18 Community con experiencia móvil.
Usa res.partner y sale.order estándar, registra múltiples tipos de negocio,
horarios estructurados, visitas con GPS y proformas sin dependencias Enterprise.
    """,
    "author": "Conedera",
    "license": "LGPL-3",
    "depends": ["contacts", "mail", "sale_management", "web"],
    "data": [
        "security/census_security.xml",
        "security/ir.model.access.csv",
        "data/census_sequence.xml",
        "data/business_type_data.xml",
        "views/res_partner_views.xml",
        "views/census_visit_views.xml",
        "views/sale_order_views.xml",
        "views/census_menus.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "conedera_odoo_census/static/src/js/gps_capture_field.js",
            "conedera_odoo_census/static/src/xml/gps_capture_field.xml",
            "conedera_odoo_census/static/src/scss/census_mobile.scss",
        ],
    },
    "application": True,
    "installable": True,
}
