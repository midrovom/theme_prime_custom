# -*- coding: utf-8 -*-
{
    'name': "api_administrator",
    "version": "18.0.1.0.0",
    'summary': """
        Controla las Apis - Radis""",

    'description': """
        Odoo18 cm
        Mantenedor de apis .
        Configure las apis de sus módulos para poder manipularlas desde aqui
        Ingrese los diferentes end poins de su modulo y mandelo allamar desde api
        para las funciones que manejen stock debes seleccionar is_stock_update ,
        caso contrario no son tomadas encuenta para actualizar el stock
        Si la api alimenta el stock debes crear una lista lista de precios para asignar los precios
        de otra forma solo actualizara los price list del producto ( El precio del producto)
    """,

    'author': "Callphone",
    'website': "https://www.callphone.com.ec",
    'images': ['static/description/banner.png'],
    "category": "",
    "depends": ['base','stock'],
    "license": "AGPL-3",
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'views/api_adminitrator_view.xml',
    ],
    'license': 'AGPL-3',
    'post_load': '',
    "installable": True,
    'auto_install': False,
    'application': True,
}
