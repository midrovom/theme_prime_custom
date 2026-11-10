# -*- coding: utf-8 -*-
"""Clasificar los registros antiguos sin alterar sus datos de auditoría."""


def migrate(cr, version):
    cr.execute("""
        UPDATE maintenance_equipment_bodega_history
           SET movement_type = 'employee_to_warehouse'
         WHERE movement_type IS NULL
    """)
