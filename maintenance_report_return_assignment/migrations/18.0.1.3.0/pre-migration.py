# -*- coding: utf-8 -*-
"""Retire legacy contact/warehouse views before updating from 18.0.1.2.0.

They referenced fields removed in this release. New installations have neither
view, so nothing needs to be migrated.
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
