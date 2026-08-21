{
    "name": "Ofertas Web por Sitio",
    "summary": "Permite negociar ofertas por producto sin alterar el carrito ni los precios públicos",
    "version": "18.0.1.0.0",
    "category": "Website/eCommerce",
    "author": "Callphone",
    "website": "https://callphone.ec",
    "license": "LGPL-3",
    "depends": [
        "mail",
        "portal",
        "sale_management",
        "website_sale_stock",
    ],
    "data": [
        "security/offer_security.xml",
        "security/ir.model.access.csv",
        "data/offer_sequence.xml",
        "data/offer_mail_templates.xml",
        "views/res_config_settings_views.xml",
        "views/offer_rule_views.xml",
        "views/offer_views.xml",
        "views/sale_order_views.xml",
        "views/website_templates.xml",
        "views/portal_templates.xml",
    ],
    "assets": {
        "web.assets_frontend": [
            "website_product_offer/static/src/scss/product_offer.scss",
            "website_product_offer/static/src/js/product_offer.js",
        ],
    },
    "application": True,
    "installable": True,
    "auto_install": False,
}

