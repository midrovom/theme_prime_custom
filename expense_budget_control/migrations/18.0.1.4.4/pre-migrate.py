# -*- coding: utf-8 -*-
"""Actualización desde v1.4.3: conservar presupuestos cerrados y liberar rubros."""

def migrate(cr, version):
    # No se eliminan presupuestos: Cerrado pasa a Aprobado.
    cr.execute("UPDATE expense_budget SET state = 'approved' WHERE state = 'closed'")
    # La versión anterior imponía un solo presupuesto por empresa/año.
    # Quitar la restricción existente permite otro rubro tras la aprobación.
    try:
        from odoo.upgrade import util
    except ImportError:
        cr.execute(
            'ALTER TABLE expense_budget '
            'DROP CONSTRAINT IF EXISTS expense_budget_year_company_unique'
        )
        # En instalaciones sin odoo.upgrade, limpiar también la metadata ORM.
        cr.execute('''
            DELETE FROM ir_model_data
            WHERE model = 'ir.model.constraint'
              AND res_id IN (
                  SELECT id FROM ir_model_constraint
                  WHERE name = 'expense_budget_year_company_unique'
              )
        ''')
        cr.execute('''
            DELETE FROM ir_model_constraint
            WHERE name = 'expense_budget_year_company_unique'
        ''')
    else:
        util.remove_constraint(cr, 'expense_budget', 'year_company_unique', warn=False)
