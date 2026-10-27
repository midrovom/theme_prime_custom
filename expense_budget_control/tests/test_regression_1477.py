# -*- coding: utf-8 -*-
"""1.4.77: omitir valores en las filas agrupadoras del PDF mensual."""
from lxml import html

from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestComparisonMonthlyGroupValues1477(TransactionCase):
    def _render_cells(self, row_class):
        """Usar la misma plantilla de QWeb que renderiza el informe PDF."""
        row_data = {
            'monthly_report': {
                'openings': {2: 143.84},
                'cells': {2: {
                    'planned': 260.0,
                    'actual': 202.12,
                    'available': 57.88,
                }},
                'period_closings': {2: {
                    'saldo_actual': 202.12,
                    'consumo_actual': 209.12,
                    'saldo_disponible': 201.72,
                }},
            }
        }
        rendered = self.env['ir.qweb']._render(
            'expense_budget_control.report_comparison_monthly_row',
            {
                'row_class': row_class,
                'row_name': 'Agua',
                'row_data': row_data,
                'page_data': {
                    'opening': True,
                    'months': [{'number': 2, 'name': 'FEBRERO'}],
                    'first_month': 2,
                },
            },
        )
        markup = rendered.decode('utf-8') if isinstance(rendered, bytes) else str(rendered)
        tr = html.fragment_fromstring(markup.strip())
        return [td.text_content().strip() for td in tr.xpath('./td')]

    def test_category_and_account_rows_only_show_names(self):
        for row_class in ('category-row', 'account-row'):
            with self.subTest(row_class=row_class):
                cells = self._render_cells(row_class)
                self.assertEqual(len(cells), 9)
                self.assertEqual(cells[0], 'Agua')
                self.assertEqual(cells[1:], [''] * 8)

    def test_detail_and_total_rows_keep_their_amounts(self):
        for row_class in ('budget-row', 'grand-row'):
            with self.subTest(row_class=row_class):
                cells = self._render_cells(row_class)
                self.assertEqual(len(cells), 9)
                self.assertEqual(cells[0], 'Agua')
                self.assertEqual(cells[1:5], [
                    '143.84', '260.00', '202.12', '57.88',
                ])
                self.assertEqual(cells[-1], '201.72')
