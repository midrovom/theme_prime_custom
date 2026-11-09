# -*- coding: utf-8 -*-
"""Retira vistas de Contactos legadas al actualizar desde versiones antiguas.

El campo bodega_devolucion_id (res.partner) de la versión 1.4 deja de usarse;
Odoo lo retira de la definición del modelo durante la actualización normal.
No borrar datos de res.partner ni de hr.employee.
"""


def migrate(cr, version):
    names = (
        'res_partner_form_inherit_es_bodega',
        'maintenance_equipment_form_inherit_return_warehouse',
    )
    cr.execute("""
        SELECT view.id
          FROM ir_ui_view AS view
          JOIN ir_model_data AS imd
            ON imd.model = 'ir.ui.view' AND imd.res_id = view.id
         WHERE imd.module = %s AND imd.name IN %s
    """, ('maintenance_report_return_assignment', names))
    ids = [r[0] for r in cr.fetchall()]
    if ids:
        cr.execute('DELETE FROM ir_ui_view WHERE id = ANY(%s)', (ids,))
    cr.execute("""
        DELETE FROM ir_model_data
         WHERE module = %s AND model = 'ir.ui.view' AND name IN %s
    """, ('maintenance_report_return_assignment', names))
