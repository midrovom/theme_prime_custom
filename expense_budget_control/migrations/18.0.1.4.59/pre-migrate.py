# -*- coding: utf-8 -*-
def migrate(cr, version):
    cr.execute('''ALTER TABLE IF EXISTS expense_budget_line
                  DROP CONSTRAINT IF EXISTS expense_budget_line_budget_month_account_unique''')
