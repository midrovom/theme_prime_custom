{
    'name': 'Transcash - Importación de Guías ERP',
    'version': '18.0.1.7.0',
    'category': 'Inventory/Delivery',
    'summary': 'Sincroniza guías desde api.administrator con maestros y privacidad comercial',
    'license': 'LGPL-3',
    'depends': ['base', 'logistica_transcash'],
    'data': [
        'security/groups.xml',
        'security/ir.model.access.csv',
        'security/rules.xml',
        'views/guide_views.xml',
        'views/operational_ux_views.xml',
        'views/driver_contact_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'transcash_guias_api/static/src/css/guide_kanban.css',
        ],
    },
    'installable': True,
    'application': False,
}
