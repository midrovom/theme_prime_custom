{
    'name': 'Catastro - Importación ERP Excel para Loyalty y Precios',
    'summary': 'Importa políticas SKU por Excel y controla las listas de precios por usuario',
    'version': '18.0.1.0.0',
    'category': 'Sales',
    'author': 'Implementación Catastro',
    'license': 'LGPL-3',
    'depends': ['sale_management', 'sale_loyalty', 'product', 'sales_team'],
    'data': [
        'security/ir.model.access.csv',
        'security/pricelist_rules.xml',
        'views/import_views.xml',
    ],
    'application': False,
    'installable': True,
}
