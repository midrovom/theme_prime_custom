{
    "name": "Análisis de Comisiones",
    "version": "18.0.6.0.0",
    "summary": "Compras de SIM, conciliación, ROI, recuperación y rendimiento por región/zona",
    "category": "Sales/Commission Analysis",
    "author": "Telecity",
    "license": "LGPL-3",
    "depends": ["base", "mail", "web"],
    "external_dependencies": {"python": ["openpyxl"]},
    "data": [
        "security/ir.model.access.csv",
        "data/sequence.xml",
        "data/default_config.xml",
        "views/operator_views.xml",
        "views/mapping_views.xml",
        "views/scheme_views.xml",
        "views/sim_views.xml",
        "views/purchase_views.xml",
        "views/settlement_views.xml",
        "views/dashboard_views.xml",
        "views/region_analysis_views.xml",
        "wizard/import_wizard_views.xml",
        "views/menu.xml"
    ],
    "installable": True,
    "application": True
}