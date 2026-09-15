{
    "name": "Conedera - Catastro Comercial (Community)",
    "version": "18.0.1.0.0",
    "category": "Sales/Sales",
    "summary": "Catastro de clientes, visitas comerciales, GPS y proformas",
    "description": """
Catastro comercial para vendedores de campo en Odoo 18 Community.
Extiende Contactos, registra visitas con ubicación GPS y enlaza proformas de Ventas.
No requiere módulos Enterprise.
    """,
    "author": "Conedera",
    "license": "LGPL-3",
    "depends": ["contacts", "mail", "sale_management", "web"],
    "data": [
        "security/census_security.xml",
        "security/ir.model.access.csv",
        "data/census_sequence.xml",
        "views/res_partner_views.xml",
        "views/census_visit_views.xml",
        "views/sale_order_views.xml",
        "views/census_menus.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "conedera_odoo_census/static/src/js/gps_capture_field.js",
            "conedera_odoo_census/static/src/xml/gps_capture_field.xml",
        ],
    },
    "application": True,
    "installable": True,
}
