"""Retire the internal-number uniqueness constraint before registry init."""

def migrate(cr, version):
    if not version:
        return
    cr.execute("DROP INDEX IF EXISTS dispatch_invoice_current_unique")
    cr.execute("UPDATE dispatch_invoice SET is_current=false WHERE is_current")
    # Old prepared chunks and sorted raw chunks used the old grouping order.
    cr.execute("UPDATE dispatch_snapshot SET api_grouped_rows=false WHERE api_grouped_rows")
