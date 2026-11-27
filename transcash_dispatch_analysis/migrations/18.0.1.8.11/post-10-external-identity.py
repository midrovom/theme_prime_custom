"""In-place conversion. Ordinary invoices never have their details recreated."""
import base64
import json
import logging
from odoo import api, SUPERUSER_ID
from odoo.addons.transcash_dispatch_analysis.services.engine import (
    aggregate_invoice, iter_invoice_groups, unique_invoice_lines,
)
from odoo.addons.transcash_dispatch_analysis.services.external_upgrade import (
    header_plan, inspect_source, needs_staging,
)

_logger = logging.getLogger(__name__)
BATCH = 2000


def _stored_rows(snapshot):
    cr = snapshot.env.cr
    last = 0
    while True:
        cr.execute('''SELECT l.id,l.raw_data FROM dispatch_invoice_line l
                      WHERE l.snapshot_id=%s AND l.id>%s ORDER BY l.id LIMIT %s''',
                   (snapshot.id, last, BATCH))
        rows = cr.fetchall()
        if not rows:
            return
        for ident, raw in rows:
            if not raw:
                raise ValueError('Corte %s: falta el registro original de la línea %s.' % (snapshot.id, ident))
            yield json.loads(raw) if isinstance(raw, str) else raw
        last = rows[-1][0]


def _has_raw(snapshot):
    if snapshot.input_type == 'xlsx':
        return bool(snapshot.with_context(bin_size=True).raw_file)
    return bool(snapshot.env['dispatch.chunk'].search_count([
        ('snapshot_id', '=', snapshot.id), ('phase', '=', 'raw')], limit=1))


def _source_rows(snapshot):
    if snapshot.input_type == 'xlsx':
        yield from snapshot._rows()
        snapshot.invalidate_recordset(['raw_file'])
        return
    chunks = snapshot.env['dispatch.chunk'].search([
        ('snapshot_id', '=', snapshot.id), ('phase', '=', 'raw')], order='sequence')
    for ident in chunks.ids:
        chunk = chunks.browse(ident).with_context(bin_size=False)
        yield from json.loads(base64.b64decode(chunk.payload))
        chunk.invalidate_recordset(['payload'])


def _stage(cr, snapshot_id):
    # A non-JSON namespace cannot collide with either invoice-key format.
    cr.execute('''UPDATE dispatch_invoice SET invoice_key='external-rekey:' || id::text
                  WHERE snapshot_id=%s''', (snapshot_id,))


def _rename(cr, items):
    """Bulk SQL updates preserve record IDs, detail, stored SLA and weights."""
    for start in range(0, len(items), BATCH):
        batch = items[start:start+BATCH]
        placeholders = ','.join(['(%s,%s,%s,%s)'] * len(batch))
        cr.execute('''UPDATE dispatch_invoice i SET invoice_key=v.key, name=v.label,
                      external_number=v.external FROM (VALUES ''' + placeholders + ''')
                      AS v(id,key,label,external) WHERE i.id=v.id::integer
                      AND (i.invoice_key,i.name,i.external_number) IS DISTINCT FROM
                          (v.key,v.label,v.external)''',
                   [value for item in batch for value in (item[0], item[2], item[3], item[4])])


def _rebuild_group(snapshot, invoices, key, rows, candidates):
    summary = aggregate_invoice(key, rows, snapshot.cutoff_date)
    mapping = snapshot.env['dispatch.warehouse']._ensure_records(snapshot.company_id, rows)
    vals = snapshot._invoice_values({'summary': summary, 'lines': rows}, mapping)
    if candidates:
        # Preserve a stable header ID where possible. Only exceptional groups
        # have their details rebuilt, using the original row order if available.
        keeper = invoices.browse(candidates[0][0])
        obsolete = invoices.browse([item[0] for item in candidates[1:]])
        if obsolete:
            obsolete.unlink()
        keeper.write({**vals, 'line_ids': [(5, 0, 0), *vals['line_ids']]})
    else:
        invoices.create(vals)


def _convert_snapshot(snapshot, invoices):
    env, cr = snapshot.env, snapshot.env.cr
    cr.execute('''SELECT id,invoice_key,external_number,invoice_type,internal_number,line_count,name
                  FROM dispatch_invoice WHERE snapshot_id=%s ORDER BY id''', (snapshot.id,))
    groups, by_old = header_plan(cr.fetchall())
    collisions = {key for key, items in groups.items() if len(items) > 1}
    # The old header came from the first detail. Compare raw external values
    # without loading every JSON object into Python or the Odoo cache.
    cr.execute('''SELECT EXISTS(SELECT 1 FROM dispatch_invoice i
                  JOIN dispatch_invoice_line l ON l.invoice_id=i.id
                  WHERE i.snapshot_id=%s AND l.raw_data IS NOT NULL
                  AND coalesce(l.raw_data->>'Factura','') IS DISTINCT FROM
                      coalesce(i.external_number,''))''', (snapshot.id,))
    mixed = cr.fetchone()[0]
    raw_available = _has_raw(snapshot) if (collisions or mixed or snapshot.duplicate_rows or not groups) else False
    # Old deduplication may have hidden a split. Check original rows if available.
    exceptional = bool(collisions or mixed or (raw_available and (snapshot.duplicate_rows or not groups)))
    if not groups and not raw_available and snapshot.total_rows:
        raise ValueError('Corte %s: no hay facturas ni original para recuperar las líneas.' % snapshot.id)
    # Most duplicate rows are ordinary repeated observations under the same
    # identity. A streaming inspection is sufficient when there is no split;
    # do not sort or aggregate a whole historical export in that case.
    if exceptional and raw_available and groups and not collisions and not mixed:
        dirty, received = set(), [0]
        for _row in inspect_source(_source_rows(snapshot), groups, by_old, dirty, received):
            pass
        if snapshot.total_rows and received[0] != snapshot.total_rows:
            raise ValueError('Corte %s: el original no coincide con el total de líneas guardado.' % snapshot.id)
        exceptional = bool(dirty)
    if not exceptional:
        if needs_staging(groups, by_old):
            _stage(cr, snapshot.id)
        _rename(cr, [items[0] for items in groups.values()])
        return len(groups), 0

    _stage(cr, snapshot.id)
    invoices.invalidate_model(['invoice_key', 'name', 'external_number'])
    dirty, received = set(collisions), [0]
    clean, seen = [], set()
    count = duplicates = updates = rebuilt = 0
    source = _source_rows(snapshot) if raw_available else _stored_rows(snapshot)
    try:
        for key, rows in iter_invoice_groups(inspect_source(source, groups, by_old, dirty, received)):
            unique, removed, changed = unique_invoice_lines(rows)
            candidates = groups.get(key, [])
            seen.add(key)
            count += 1
            duplicates += removed
            updates += changed
            if key not in dirty and len(candidates) == 1 and candidates[0][5] == len(unique):
                clean.append(candidates[0])
            else:
                _rebuild_group(snapshot, invoices, key, unique, candidates)
                rebuilt += 1
                if rebuilt % 100 == 0:
                    env.flush_all()
                    env.invalidate_all()
        if raw_available and snapshot.total_rows and received[0] != snapshot.total_rows:
            raise ValueError('Corte %s: el original no coincide con el total de líneas guardado.' % snapshot.id)
        if not seen and groups:
            raise ValueError('Corte %s: no se encontraron filas para reconstruir.' % snapshot.id)
        missing = set(groups) - seen
        if missing:
            if not raw_available:
                raise ValueError('Corte %s: no se pudo recuperar toda la información de las facturas.' % snapshot.id)
            # A former header may no longer correspond to any external group.
            invoices.browse([item[0] for key in missing for item in groups[key]]).unlink()
        env.flush_all()
        _rename(cr, clean)
        invoices.invalidate_model(['invoice_key', 'name', 'external_number'])
        vals = {'total_invoices': count, 'loaded_invoices': count}
        if raw_available:
            vals.update(duplicate_rows=duplicates, duplicate_updates=updates)
        snapshot.write(vals)
        return count, rebuilt
    finally:
        # Explicitly release the source generator on error as well.
        source.close()


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {'bin_size': False, 'active_test': False})
    invoices = env['dispatch.invoice']
    snapshots = env['dispatch.snapshot']
    # Fail promptly if a sync is running; do not wait indefinitely holding DDL
    # locks. The deployment instructions recommend stopping all Odoo workers.
    for company in env['res.company'].search([], order='id'):
        cr.execute('SELECT pg_try_advisory_xact_lock(%s,%s)', (180107, company.id))
        if not cr.fetchone()[0]:
            raise ValueError('Hay una sincronización de despachos en curso. Deténgala antes de actualizar.')
    cr.execute('UPDATE dispatch_invoice SET is_current=false WHERE is_current')
    invoices.invalidate_model(['is_current'])
    # Leave disposable partial details in place: _prepare will remove them in
    # the existing import worker, not during module installation.
    snapshots.search([('state', '=', 'loading')]).write({
        'state': 'queued', 'loaded_invoices': 0, 'total_invoices': 0,
        'error_message': False, 'api_grouped_rows': False})
    env.flush_all()
    ids = snapshots.search([('state', 'in', ['ready', 'archived'])], order='id').ids
    _logger.info('Despachos: conversión externa en sitio de %s cortes', len(ids))
    for ident in ids:
        snapshot = snapshots.browse(ident)
        count, rebuilt = _convert_snapshot(snapshot, invoices)
        env.flush_all()
        env.invalidate_all()
        _logger.info('Despachos: corte %s: %s facturas, %s grupos recalculados', ident, count, rebuilt)
    # The same ranking as latest_invoice_versions, but performed in PostgreSQL.
    cr.execute('''UPDATE dispatch_invoice i SET is_current=true FROM (
        SELECT DISTINCT ON (i.company_id,i.invoice_key) i.id
        FROM dispatch_invoice i JOIN dispatch_snapshot s ON s.id=i.snapshot_id
        JOIN dispatch_source src ON src.id=s.source_id AND src.active_snapshot_id=s.id
        WHERE s.state='ready'
        ORDER BY i.company_id,i.invoice_key,s.cutoff_date DESC,s.id DESC,i.id DESC
        ) winners WHERE i.id=winners.id''')
    invoices.invalidate_model(['is_current'])
    _logger.info('Despachos: conversión externa finalizada; se conservan las facturas sin conflictos')
