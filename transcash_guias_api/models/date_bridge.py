"""ERP date-only bridge into Odoo UTC datetimes, preserving local calendar day.

ERP dates are *planned* calendar values, not measured timestamps. The generated
midnight is a technical placeholder and must never be treated as a real departure.
"""
from datetime import date, datetime, time, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def normalize_erp_date(value):
    """Return YYYY-MM-DD or None. Supports ERP formats and Python date types."""
    if value is None or value is False or value == '':
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    raw = str(value).strip()
    if not raw:
        return None
    datepart = raw.split(' ', 1)[0].split('T', 1)[0]
    from re import fullmatch
    m = fullmatch(r'(\d{4})[./-](\d{1,2})[./-](\d{1,2})', datepart)
    if m:
        y, mo, d = map(int, m.groups())
    else:
        m = fullmatch(r'(\d{1,2})[./-](\d{1,2})[./-](\d{4})', datepart)
        if not m:
            raise ValueError('Fecha ERP no reconocida: %s' % raw)
        d, mo, y = map(int, m.groups())
    return date(y, mo, d).isoformat()


def date_as_odoo_utc(value, tz_name='America/Guayaquil'):
    """Return UTC-naive Odoo DATETIME string for midnight on ERP calendar day.

    The timestamp is a placeholder, not an actual departure/arrival measurement.
    """
    iso = normalize_erp_date(value)
    if not iso:
        return False
    try:
        tz = ZoneInfo(tz_name or 'America/Guayaquil')
    except (ZoneInfoNotFoundError, ValueError):
        tz = ZoneInfo('America/Guayaquil')
    local = datetime.combine(date.fromisoformat(iso), time.min, tzinfo=tz)
    return local.astimezone(timezone.utc).replace(tzinfo=None).strftime('%Y-%m-%d %H:%M:%S')
