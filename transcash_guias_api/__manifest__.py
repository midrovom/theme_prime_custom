{
    'name': 'Transcash - Importación de Guías ERP',
    'version': '18.0.1.3.0',
    'category': 'Inventory/Delivery',
    'summary': 'Sincroniza guías desde api.administrator con maestros y privacidad comercial',
    'license': 'LGPL-3',
    'depends': ['base', 'logistica_transcash'],
    'data': [
        'security/groups.xml',
        'security/ir.model.access.csv',
        'security/rules.xml',
        'views/guide_views.xml',
    ],
    'installable': True,
    'application': False,
}
