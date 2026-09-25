{
    "name": "Transcash Commissions - Reglas Avanzadas",
    "summary": "Extiende liquidación, gestión de administradores y proyectos sin modificar el módulo principal",
    "version": "18.0.1.0.0",
    "category": "Sales/Commissions",
    "author": "Transcash",
    "license": "LGPL-3",
    "depends": [
        "transcash_commission_goal_rules",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/advanced_rules_views.xml",
    ],
    "installable": True,
    "application": False,
}
