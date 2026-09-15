{
    "name": "Transcash Commissions - API Administrator Bridge",
    "summary": "Conecta la sincronización de comisiones con api.administrator",
    "version": "18.0.1.0.1",
    "category": "Sales/Commissions",
    "author": "Transcash",
    "license": "LGPL-3",
    "depends": [
        "transcash_commission",
        "api_administrator",
    ],
    "external_dependencies": {"python": ["requests"]},
    "data": [
        "views/commission_sync_views.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
