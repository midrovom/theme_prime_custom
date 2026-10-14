# -*- coding: utf-8 -*-
"""Reporte anual Proyectado vs. real agrupado por rubro y cuenta.

Muestra una fila por presupuesto/cuenta/año, acumulando sus doce meses.
"""

from odoo import api, models


class ReportExpenseBudgetComparison(models.AbstractModel):
    _name = 'report.expense_budget_control.report_comparison_document'
    _description = 'Reporte anual Proyectado vs. real por rubro y cuenta'

    @staticmethod
    def _empty_totals():
        return {'planned': 0.0, 'actual': 0.0, 'available': 0.0, 'execution': 0.0}

    @classmethod
    def _add_line(cls, totals, line):
        totals['planned'] += line.planned_amount
        totals['actual'] += line.actual_amount
        totals['available'] = totals['planned'] - totals['actual']
        totals['execution'] = (
            totals['actual'] / totals['planned'] * 100.0 if totals['planned'] else 0.0
        )

    @classmethod
    def _add_totals(cls, target, source):
        target['planned'] += source['planned']
        target['actual'] += source['actual']
        target['available'] = target['planned'] - target['actual']
        target['execution'] = (
            target['actual'] / target['planned'] * 100.0 if target['planned'] else 0.0
        )

    @api.model
    def _prepare_comparison(self, wizard):
        """Usar la misma vista anual que la pantalla; los permisos son los mismos.

        Sin sudo: el Aprobador no puede imprimir presupuestos borrador, incluso
        si comparten empresa/año/cuenta con otros presupuestos aprobados.
        """
        domain = [
            ('company_id', '=', wizard.company_id.id),
            ('year', '=', int(wizard.year)),
        ]
        if wizard.category_id:
            domain.append(('category_id', '=', wizard.category_id.id))
        if wizard.account_id:
            domain.append(('account_id', '=', wizard.account_id.id))

        annual_rows = self.env['expense.budget.annual.analysis'].search(domain)
        category_map = {}
        grand_total = self._empty_totals()
        line_count = 0
        account_ids = set()
        for annual in annual_rows:
            category, account = annual.category_id, annual.account_id
            account_ids.add(account.id)
            if category.id not in category_map:
                category_map[category.id] = {
                    'category': category, 'accounts_map': {},
                    'line_count': 0, 'annual_count': 0, 'total': self._empty_totals(),
                }
            group = category_map[category.id]
            if account.id not in group['accounts_map']:
                group['accounts_map'][account.id] = {
                    'account': account, 'lines': [], 'line_count': 0, 'annual_count': 0,
                    'total': self._empty_totals(),
                }
            account_group = group['accounts_map'][account.id]
            account_group['lines'].append(annual)
            account_group['annual_count'] += 1
            group['annual_count'] += 1
            account_group['line_count'] += annual.line_count
            group['line_count'] += annual.line_count
            line_count += annual.line_count
            self._add_line(account_group['total'], annual)

        categories = []
        for group in sorted(category_map.values(), key=lambda item: (
                item['category'].code or '', item['category'].name or '', item['category'].id)):
            group['accounts'] = sorted(group.pop('accounts_map').values(), key=lambda item: (
                item['account'].code or '', item['account'].name or '', item['account'].id))
            for account in group['accounts']:
                account['lines'].sort(key=lambda line: (
                    line.budget_id.name or '', line.budget_id.id,
                ))
                self._add_totals(group['total'], account['total'])
            self._add_totals(grand_total, group['total'])
            categories.append(group)

        return {
            'wizard': wizard,
            'categories': categories,
            'grand_total': grand_total,
            'line_count': line_count,  # cantidad de proyecciones mensuales acumuladas
            'account_count': len(account_ids),
            'budget_account_count': len(annual_rows),
        }

    @api.model
    def _get_report_values(self, docids, data=None):
        wizards = self.env['expense.budget.comparison.report.wizard'].browse(docids).exists()
        wizards.check_access('read')
        return {
            'doc_ids': wizards.ids,
            'doc_model': 'expense.budget.comparison.report.wizard',
            'docs': wizards,
            'reports': [self._prepare_comparison(wizard) for wizard in wizards],
        }
