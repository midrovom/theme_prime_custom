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
    "depends": ['stock'],
    "license": "AGPL-3",
    'data': [

    ],
    'license': 'AGPL-3',
    'post_load': '',
    "installable": True,
    'auto_install': True,
    'application': True,
}
