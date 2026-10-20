{
    'name': 'TRANSCASH | Inventario Inteligente',
    'summary': 'Dashboard HTML de compras, stock, ABC, rentabilidad y reposición con importación XLSX',
    'version': '18.0.1.2.0',
    'category': 'Inventory/Reporting',
    'author': 'RADIS / Solución personalizada',
    'license': 'LGPL-3',
    'depends': ['base', 'web'],
    'data': [
        'security/groups.xml',
        'security/ir.model.access.csv',
        'security/rules.xml',
        'security/upload_rules.xml',
        'data.xml',
        'views/snapshot_views.xml',
        'views/import_views.xml',
        'views/menu.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'transcash_inventory/static/src/odoo_action.js',
            'transcash_inventory/static/src/odoo_action.xml',
            'transcash_inventory/static/src/odoo_action.css',
        ],
    },
    'application': True,
    'installable': True,
}
