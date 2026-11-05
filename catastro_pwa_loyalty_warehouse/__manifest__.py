{
    'name': 'Catastro PWA - Promociones Loyalty por bodega',
    'summary': 'Restringe programas Loyalty de Ventas a las bodegas asignadas en cada promoción',
    'version': '18.0.1.0.0',
    'category': 'Sales',
    'license': 'LGPL-3',
    'depends': ['catastro_pwa_loyalty_bridge', 'sale_loyalty', 'sale_stock'],
    'data': ['views/loyalty_program_views.xml'],
    'installable': True,
    'application': False,
    'auto_install': False,
}
