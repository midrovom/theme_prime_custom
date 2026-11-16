# -*- coding: utf-8 -*-
"""Remove obsolete inherited views on upgrade from 1.1/1.2.

The previous "Es bodega" and "Empleado asociado a bodega" fields were
removed from Contactos in 1.3; if an upgrade skips 1.3 this cleans their
views before Odoo validates the new registry. No contact data is removed.
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
    view_ids = [rec[0] for rec in cr.fetchall()]
    if view_ids:
        cr.execute('DELETE FROM ir_ui_view WHERE id = ANY(%s)', (view_ids,))
    cr.execute("""
        DELETE FROM ir_model_data
         WHERE module = %s AND model = 'ir.ui.view' AND name IN %s
    """, ('maintenance_report_return_assignment', names))
