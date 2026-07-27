{
    "name": "Billetera de Recompensas para Clientes",
    "version": "18.0.1.0.0",
    "summary": "Control independiente de dólares acumulados y consulta móvil en el portal",
    "description": """
Billetera independiente de contabilidad para registrar recompensas de clientes.
Permite abonos, consumos, ajustes, reversos auditables y consulta desde el portal móvil.
    """,
    "category": "Sales/CRM",
    "author": "Custom Development",
    "website": "https://www.odoo.com",
    "license": "LGPL-3",
    "depends": ["base", "contacts", "mail", "portal"],
    "data": [
        "security/wallet_security.xml",
        "security/ir.model.access.csv",
        "data/sequence_data.xml",
        "views/wallet_views.xml",
        "views/partner_views.xml",
        "views/portal_templates.xml",
        "views/menu_views.xml"
    ],
    "assets": {
        "web.assets_frontend": [
            "customer_loyalty_wallet/static/src/scss/portal_wallet.scss"
        ]
    },
    "images": ["static/description/icon.png"],
    "installable": True,
    "application": True,
    "auto_install": False
}
