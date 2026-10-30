"""Bounded import tuning. Business calculations stay in the shared engine."""
from .engine import invoice_key

BACKGROUND_BATCH_SIZE = 500
BACKGROUND_MIN_SIZE = 50
BACKGROUND_LINE_RATIO = 5
BACKGROUND_TARGET_SECONDS = 3.0
CRON_BUDGET_SECONDS = 6.0
CRON_MAX_STEPS = 20


def background_limits(size):
    size = max(BACKGROUND_MIN_SIZE, min(BACKGROUND_BATCH_SIZE, int(size or BACKGROUND_BATCH_SIZE)))
    return size, size * BACKGROUND_LINE_RATIO


def next_background_size(size, processed, seconds):
    """Adapt to observed work, growing by at most 2x; no fixed-time promise.

    `seconds` includes the savepoint flush, not just Python value construction.
    The last short portion of a prepared chunk must not shrink a healthy batch.
    """
    size, _ = background_limits(size)
    if processed <= 0 or seconds <= 0:
        return size
    if processed < size and seconds <= BACKGROUND_TARGET_SECONDS:
        return size
    target = int(processed * BACKGROUND_TARGET_SECONDS / seconds)
    return max(BACKGROUND_MIN_SIZE, min(BACKGROUND_BATCH_SIZE, size * 2, target))


def iter_presorted_invoice_groups(rows):
    """Stream trusted, stably sorted API intake across raw chunk boundaries.

    Validate order before publishing anything. A false marker/corrupt intake
    cannot silently split an invoice or replace the current snapshot.
    """
    previous, group = None, []
    for count, row in enumerate(rows, 1):
        if not isinstance(row, dict):
            raise ValueError("Cada registro debe ser un objeto con columnas del exportador.")
        if count > 500_000:
            raise ValueError("El lote supera 500.000 líneas.")
        key = invoice_key(row)
        if previous is not None and key < previous:
            raise ValueError("La secuencia API agrupada no es válida. El corte vigente se conserva.")
        if previous is not None and key != previous:
            yield previous, group
            group = []
        group.append(row)
        previous = key
    if group:
        yield previous, group
