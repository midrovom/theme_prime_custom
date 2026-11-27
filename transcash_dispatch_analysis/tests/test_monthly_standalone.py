"""Annual charts: same unique invoices and SLA policy as the dashboard."""
import unittest
from types import SimpleNamespace
from test_dashboard_standalone import Environment, data, module
from dispatch_queue_test.services.monthly import monthly_dispatch
from dispatch_queue_test.services.engine import evaluate, invoice_key


class MonthlyTests(unittest.TestCase):
    def row(self, identity, start, end=False, pending=False, **extra):
        row = dict(id=identity, name=str(identity), invoice_date=start, completion_date=end,
                   cutoff_date='2026-11-27', pending=pending, physically_completed=bool(end),
                   city='GUAYAQUIL', delivery='Entrega Transcash', quality_issue=False, has_adjustment=False)
        row.update(extra)
        return evaluate(row, {'rules': [{'max_days': 3, 'day_type': 'calendar'}]} if not extra.get('no_sla') else {})

    def test_twelve_months_and_exact_running_sum(self):
        rows = [self.row(i, '2026-01-05', pending=True) for i in range(1, 6)]
        rows += [self.row(i, '2026-02-05', pending=True) for i in range(6, 9)]
        rows += [self.row(i, '2026-03-05', pending=True) for i in range(9, 11)]
        rows += [self.row(11, '2025-12-01', pending=True), self.row(12, '2026-01-03', '2026-02-03')]
        result = monthly_dispatch(rows, 2026)
        self.assertEqual(len(result['months']), 12)
        self.assertEqual([m['pending_accumulated'] for m in result['months']], [5, 8] + [10] * 10)
        self.assertEqual(result['pending_total'], 10)
        self.assertEqual(result['months'][1]['completed'], 1)

    def test_actual_completion_month_and_sla_coverage(self):
        rows = [self.row(1, '2025-12-30', '2026-01-02'),
                self.row(2, '2026-01-01', '2026-01-10'),
                self.row(3, '2026-01-01', '2026-01-02', no_sla=True),
                self.row(4, '2026-01-31', '2026-02-03'),
                self.row(5, '2026-02-01', pending=True),
                self.row(6, '2026-02-01', '2026-12-01'), # after cutoff
                self.row(7, '2026-03-01', '2026-03-02', quality_issue=True)]
        jan, feb, mar, apr, *_ = monthly_dispatch(rows, 2026)['months']
        self.assertEqual((jan['completed'], jan['measured'], jan['late'], jan['late_pct']), (3, 2, 1, 50))
        self.assertEqual((feb['completed'], feb['late_pct'], feb['pending']), (1, 0, 1))
        self.assertEqual((mar['completed'], mar['measured'], mar['late_pct']), (1, 0, None))
        self.assertEqual((apr['completed'], apr['late_pct']), (0, None))

    def test_real_dashboard_annual_scope_separate_from_daily_filter(self):
        rows, lines = data()
        # A cross-year invoice is still counted when physically completed in January.
        old = {**rows[0], 'id': 10, 'invoice_date': '2025-12-31', 'completion_date': '2026-01-02',
               'deadline': '2026-01-03'}
        rows.append(old)
        rows.append({**rows[0], 'id': 11, 'company_id': [2, 'Other']})
        rows.append({**rows[0], 'id': 12, 'is_current': False})
        rows.append({**rows[0], 'id': 13, 'city': 'QUITO'})
        service = module.DispatchDashboard(); service.env = Environment(rows, lines)
        result = service.get_data({'date_from': '2026-02-01', 'date_to': '2026-02-28', 'city': 'GUAYAQUIL'})
        self.assertEqual(result['stats']['total'], 2)
        self.assertEqual(result['monthly']['months'][0]['completed'], 2)
        self.assertEqual(result['monthly']['months'][1]['pending_accumulated'], 2)
        self.assertEqual(result['monthly']['year'], 2026)
        self.assertEqual(service.get_data({'date_from':'2025-01-01','date_to':'2025-12-31'})['monthly']['year'], 2025)

    def test_warehouse_scope_cross_year_uses_actual_selected_lines(self):
        rows, lines = data()
        raw = {'TipoFactura':'FA','NumeroFactura':'9','Ciudad':'GUAYAQUIL','Cond_Entrega':'Entrega Transcash',
               'FechaFactura':'2025-12-31','Facturado':1,'DespachoFisico':1,'Pendiente':0,'UltimoDespacho':'2026-01-02'}
        rows[:] = [{**rows[1], 'id':9, 'invoice_date':'2025-12-31','invoice_key':invoice_key(raw),
                    'snapshot_id':[1,'Cut'],'warehouse_ids':[10,20],'line_dispatch_dates':['2026-01-02']}]
        lines[:] = [{'id': 1, 'invoice_id':[9,'FA'], 'warehouse_id':[10,'A'], 'raw_data':{**raw,'CodBodega':'10'}},
                    {'id': 2, 'invoice_id':[9,'FA'], 'warehouse_id':[20,'B'], 'raw_data':{**raw,'CodBodega':'20','DespachoFisico':0,'Pendiente':1,'UltimoDespacho':False}}]
        service = module.DispatchDashboard(); service.env = Environment(rows, lines)
        service.env.models['dispatch.snapshot'].browse = lambda ids: [SimpleNamespace(id=1, policy_pack={'rules':[{'max_days':3,'day_type':'calendar'}]})]
        one = service._annual_statistics({'warehouse_ids':[10],'date_to':'2026-02-28'})
        both = service._annual_statistics({'warehouse_ids':[10,20],'date_to':'2026-02-28'})
        self.assertEqual(one['months'][0]['completed'], 1)
        self.assertEqual(both['completed_total'], 0)
        self.assertEqual(both['pending_total'], 0) # prior-year backlog is outside this year's cohort

    def test_empty_year_and_large_scope(self):
        result = monthly_dispatch([], 2026)
        self.assertEqual(result['completed_total'], 0)
        self.assertTrue(all(m['late_pct'] is None and m['pending_accumulated'] == 0 for m in result['months']))
        service = module.DispatchDashboard(); service.env = Environment([], [])
        service.env.models['dispatch.invoice'].search_count = lambda domain: 200001
        self.assertFalse(service._annual_statistics({'date_to':'2026-01-01'})['available'])


if __name__ == '__main__':
    unittest.main()
