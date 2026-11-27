"""Annual dispatch completion and outstanding-invoice cohorts at the selected cut."""
from .engine import as_date
from .timeliness import dispatch_timeliness

MONTHS = ('Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic')


def monthly_dispatch(rows, year):
    months = [{'month': i, 'label': label, 'completed': 0, 'measured': 0,
               'late': 0, 'late_pct': None, 'pending': 0, 'pending_accumulated': 0}
              for i, label in enumerate(MONTHS, 1)]
    completed = [[] for _ in months]
    for row in rows:
        start = as_date(row.get('invoice_date'))
        end = as_date(row.get('completion_date'))
        cutoff = as_date(row.get('cutoff_date'))
        if row.get('pending') and start and start.year == year and cutoff and start <= cutoff:
            months[start.month - 1]['pending'] += 1
        if (row.get('physically_completed') and not row.get('pending') and end
                and end.year == year and start and cutoff and start <= end <= cutoff):
            completed[end.month - 1].append(row)
    running = 0
    for month, cohort in zip(months, completed):
        # Use exactly the same SLA eligibility and late classification as the pie.
        pie = dispatch_timeliness(cohort)['pie']
        month['completed'] = len(cohort)
        month['measured'] = pie['total']
        month['late'] = pie['series'][1]['value']
        month['late_pct'] = pie['series'][1]['pct']
        running += month['pending']
        month['pending_accumulated'] = running
    return {'year': year, 'available': True, 'months': months,
            'pending_total': running, 'completed_total': sum(m['completed'] for m in months)}
