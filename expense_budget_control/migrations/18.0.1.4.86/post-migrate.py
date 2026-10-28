# -*- coding: utf-8 -*-


def migrate(cr, version):
    # Existing records used the original annual_amount / 12 rule. Preserve that
    # behavior when the per-allocation month-count fields are introduced.
    cr.execute("""
        UPDATE expense_budget_annual_target
           SET distribution_month_count = 12
         WHERE distribution_month_count IS NULL OR distribution_month_count < 1
    """)
    cr.execute("""
        UPDATE expense_budget_line
           SET allocation_month_count = 12
         WHERE allocation_month_count IS NULL OR allocation_month_count < 1
    """)
