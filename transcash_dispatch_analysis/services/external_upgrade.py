"""Small pure helpers for the in-place external identity upgrade."""
from collections import defaultdict
import json
from .engine import external_invoice_number, invoice_display_name, invoice_key, normalize


def header_plan(rows):
    """Rows: id, previous key, external, type, internal, line count, name."""
    groups = defaultdict(list)
    by_old = {}
    for ident, old, external, kind, internal, count, name in rows:
        row = {'Factura': external, 'TipoFactura': kind, 'NumeroFactura': internal}
        key = invoice_key(row)
        item = (ident, old, key, invoice_display_name(row), external_invoice_number(external), count, name, external)
        groups[key].append(item)
        by_old[old] = item
    return groups, by_old


def legacy_key(row):
    return json.dumps([normalize(row.get('TipoFactura')), str(row.get('NumeroFactura') or '').strip()],
                      ensure_ascii=False, separators=(',', ':'))


def inspect_source(rows, groups, by_old, dirty, counter):
    """The sorter consumes the entire stream before yielding a group.

    Detect splits even if the old duplicate-line policy discarded their evidence
    in the stored detail. Mark both sides so the old summary is never reused.
    """
    for row in rows:
        key = invoice_key(row)
        old = by_old.get(legacy_key(row))
        if old is None:
            old = by_old.get(key)
        if old is None:
            dirty.add(key)
        elif old[2] != key:
            dirty.update((old[2], key))
        counter[0] += 1
        yield row


def needs_staging(groups, by_old):
    return any(key in by_old and by_old[key][2] != key for key in groups)
