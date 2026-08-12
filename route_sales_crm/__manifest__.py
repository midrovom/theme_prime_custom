{
    "name": "CRM Ventas en Ruta",
    "version": "18.0.1.0.0",
    "summary": "Clientes multisucursal, rutas, visitas GPS, cotizaciones, cobranzas y encuestas",
    "category": "Sales/CRM",
    "license": "LGPL-3",
    "depends": ["crm", "sale_management", "mail", "web"],
    "data": [
        "security/route_sales_security.xml",
        "security/ir.model.access.csv",
        "data/sequence.xml",
        "views/res_partner_views.xml",
        "views/route_plan_views.xml",
        "views/route_visit_views.xml",
        "views/sale_order_views.xml",
        "views/route_sales_menus.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "route_sales_crm/static/src/js/gps_capture.js",
            'route_sales_crm/static/src/js/route_visit_search_filters.js',
            "route_sales_crm/static/src/xml/gps_capture.xml",
        ],
    },
    "application": True,
    "installable": True,
}
