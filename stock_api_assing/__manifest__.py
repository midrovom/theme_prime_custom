# -*- coding: utf-8 -*-
{
    'name': "stock_api_assing",
    "version": "18.0.1.0.0",
    'summary': """
        update stock/ crea cotizaciones - Radiss""",

    'description': """
        1-actualiza y crea el stock desde radis (Update stock)
        * se debe crear las bodegas y asignar la compania que contiene las bodegas que vienene del api
        * lo actualiza por empresa y cada empresa debe tener su porpio endpoint
        * se actualiza cada 30 min
        * seleccion multiple de productos a cotizar
        
        2-exporta ordenes de compra creadas en odoo a radis (quotes_api)
    """,
    'author': "Callphone",
    'website': "https://www.callphone.com.ec",
    'images': ['static/description/banner.png'],
    "category": "Warehouse",
    "depends": ['base','stock','sale_management','api_administrator', 'product', 'sale_stock'],
    "license": "AGPL-3",
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'data/cron.xml',
        'views/quotes_api_assing.xml',
        'views/views.xml',
        'views/product_product_form_view.xml',
        'views/sale_view_order_form.xml',
        'views/api_administrator _inherint.xml',
        'wizard/select_product.xml',
    ],
    'license': 'AGPL-3',
    # 'assets': {
    #     'web.assets_backend': [
    #         'stock_api_assing/static/src/scss/style_tree.scss',
    #         'stock_api_assing/static/src/js/tree_button.js',
    #         # 'stock_api_assing/static/src/js/hide_add_line.js',
    #         # 'stock_api_assing/static/src/views/*',
    #         'stock_api_assing/static/src/views/**/*',
    #         # 'stock_api_assing/static/src/views/form/form_controller.scss',
    #     #    'button_near_create/static/src/js/kanban_button.js',
    #     ],
    #     'web.assets_qweb': [
    #         'stock_api_assing/static/src/xml/tree_button.xml',
    #         #'button_near_create/static/src/xml/kanban_button.xml',
    #     ],
    # },
    'post_load': '',
    "installable": True,
    'auto_install': True,
    'application': True,
}
