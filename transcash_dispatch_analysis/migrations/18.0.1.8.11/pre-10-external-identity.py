"""Retire old index and sorting marker; do not reconstruct any details."""

def migrate(cr, version):
    if not version:
        return
    # Match the import lock order (source before company). Fail rather than
    # waiting for a running synchronization while holding schema locks.
    cr.execute('SELECT id FROM dispatch_source ORDER BY id')
    sources = cr.fetchall()
    for (ident,) in sources:
        cr.execute('SELECT pg_try_advisory_xact_lock(%s,%s)', (180104, ident))
        if not cr.fetchone()[0]:
            raise ValueError('Hay una importación de despachos en curso. Deténgala antes de actualizar.')
    cr.execute('DROP INDEX IF EXISTS dispatch_invoice_current_unique')
    cr.execute('UPDATE dispatch_snapshot SET api_grouped_rows=false WHERE api_grouped_rows')
