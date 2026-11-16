# -*- coding: utf-8 -*-
"""Las devoluciones de Departamento no tienen warehouse_employee_id.

La columna estaba definida required=True antes de 18.0.1.13.0; retirar
la restricción SQL antes de crear el primer movimiento departamental.
"""


def migrate(cr, version):
    cr.execute("""
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = current_schema()
          AND table_name = 'maintenance_equipment_bodega_history'
          AND column_name = 'warehouse_employee_id'
          AND is_nullable = 'NO'
    """)
    if cr.fetchone():
        cr.execute('''
            ALTER TABLE maintenance_equipment_bodega_history
            ALTER COLUMN warehouse_employee_id DROP NOT NULL
        ''')
