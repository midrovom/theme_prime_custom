# -*- coding: utf-8 -*-
"""Quita la vista heredada del wizard antiguo antes de retirar su campo.

La versión 18.0.1.5.0 insertaba employee_id en el wizard de actas. Esa
vista dejaría de validar cuando el campo desaparezca en esta versión.
El wizard base de maintenance_report permanece sin modificaciones.
"""


def migrate(cr, version):
    names = ('view_maintenance_report_wizard_form_return_destination',)
    cr.execute("""
        SELECT view.id
          FROM ir_ui_view AS view
          JOIN ir_model_data AS imd
            ON imd.model = 'ir.ui.view' AND imd.res_id = view.id
         WHERE imd.module = %s AND imd.name IN %s
    """, ('maintenance_report_return_assignment', names))
    ids = [row[0] for row in cr.fetchall()]
    if ids:
        cr.execute('DELETE FROM ir_ui_view WHERE id = ANY(%s)', (ids,))
    cr.execute("""
        DELETE FROM ir_model_data
         WHERE module = %s AND model = 'ir.ui.view' AND name IN %s
    """, ('maintenance_report_return_assignment', names))
