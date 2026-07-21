# -*- coding: utf-8 -*-
{
    'name': "stock_update",
    "version": "18.0.1.0.0",
    'summary': """
        Actualiza automáticamente ribbon y flag de venta sin stocks""",

    'description': """
       Este módulo personalizado ajusta automáticamente los campos
        `allow_out_of_stock_order` y `website_ribbon_id` en product.template
        cuando el stock disponible llega a cero.
    """,
    'author': "Ing. Bolivar Rodriguez",
    'website': "https://www.callphone.com.ec",
    'images': ['static/description/banner.png'],
    "category": "Website",
    "depends": ['stock', 'website_sale', 'website_sale_stock'],
    "license": "AGPL-3",
    'data': [

    ],
    'post_init_hook': 'post_init_hook',
    'license': 'AGPL-3',
    "installable": True,
    'auto_install': False,
    'application': False,
}
