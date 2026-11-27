"""Rebuild historical groupings from preserved originals, keeping each cutoff/policy."""
import logging
from itertools import chain
from odoo import api, SUPERUSER_ID
from odoo.addons.transcash_dispatch_analysis.services.engine import (
    aggregate_invoice, iter_invoice_groups, unique_invoice_lines,
)

_logger = logging.getLogger(__name__)


def _stored_rows(snapshot):
    """Fallback only when the original source is not retained."""
    model = snapshot.env['dispatch.invoice.line']
    last_id = 0
    while True:
        rows = model.search([('snapshot_id', '=', snapshot.id), ('id', '>', last_id)], order='id', limit=2000)
        if not rows:
            break
        for row in rows:
            if not row.raw_data:
                raise ValueError('Corte %s: falta el detalle original de la línea %s.' % (snapshot.id, row.id))
            yield row.raw_data
        last_id = rows[-1].id


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {'bin_size': False, 'active_test': False})
    invoices = env['dispatch.invoice']
    snapshots = env['dispatch.snapshot']
    companies = env['res.company'].search([])
    for company in companies:
        cr.execute('SELECT pg_advisory_xact_lock(%s,%s)', (180107, company.id))
    # A partial import must restart grouping from raw, never mix old/new chunks.
    for snapshot in snapshots.search([('state', '=', 'loading')]):
        snapshot.invoice_ids.unlink()
        snapshot.chunk_ids.filtered(lambda c: c.phase == 'prepared').unlink()
        snapshot.write({'state': 'queued', 'loaded_invoices': 0, 'total_invoices': 0,
                        'error_message': False, 'api_grouped_rows': False})
    for snapshot in snapshots.search([('state', 'in', ['ready', 'archived'])], order='id'):
        raw_available = (bool(snapshot.raw_file) if snapshot.input_type == 'xlsx'
                         else bool(snapshot.chunk_ids.filtered(lambda c: c.phase == 'raw')))
        # Materialize grouping in the engine's disk-backed sorter before removing
        # old rows, including when stored invoice lines are the only source.
        source = snapshot._rows() if raw_available else _stored_rows(snapshot)
        groups = iter_invoice_groups(source)
        first = next(groups, None)
        if first is None and snapshot.invoice_ids:
            raise ValueError('Corte %s: no se encontraron filas para reconstruir.' % snapshot.id)
        snapshot.invoice_ids.unlink()
        count = duplicates = updates = received = 0
        batch = []
        for key, rows in chain([first] if first is not None else [], groups):
            received += len(rows)
            unique, removed, changed = unique_invoice_lines(rows)
            batch.append({'summary': aggregate_invoice(key, unique, snapshot.cutoff_date), 'lines': unique})
            count += 1
            duplicates += removed
            updates += changed
            if len(batch) >= 200:
                _create(snapshot, invoices, batch)
                batch = []
        if batch:
            _create(snapshot, invoices, batch)
        if raw_available and snapshot.total_rows and received != snapshot.total_rows:
            raise ValueError('Corte %s: el original no coincide con el total de líneas guardado.' % snapshot.id)
        counters = {'total_invoices': count, 'loaded_invoices': count}
        if raw_available:
            counters.update(duplicate_rows=duplicates, duplicate_updates=updates)
        snapshot.write(counters)
        _logger.info('Despachos: corte %s reconstruido por número externo: %s facturas (original=%s)',
                     snapshot.id, count, raw_available)
    env.flush_all()
    for company in companies:
        invoices._refresh_current_records(company.id)
    # queued imports will be resumed by the existing cron.


def _create(snapshot, invoices, batch):
    mapping = snapshot.env['dispatch.warehouse']._ensure_records(
        snapshot.company_id, [row for item in batch for row in item['lines']])
    invoices.create([snapshot._invoice_values(item, mapping) for item in batch])
