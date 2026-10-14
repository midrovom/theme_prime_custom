# -*- coding: utf-8 -*-
"""Datos del PDF de Proyectado vs. real, agrupados por rubro y cuenta."""

from odoo import api, models


class ReportExpenseBudgetComparison(models.AbstractModel):
    _name = 'report.expense_budget_control.report_comparison_document'
    _description = 'Reporte Proyectado vs. real por rubro y cuenta'

    @staticmethod
    def _empty_totals():
        return {'planned': 0.0, 'actual': 0.0, 'available': 0.0, 'execution': 0.0}

    @classmethod
    def _add_line(cls, totals, line):
        totals['planned'] += line.planned_amount
        totals['actual'] += line.actual_amount
        totals['available'] += line.variance_amount
        totals['execution'] = (
            totals['actual'] / totals['planned'] * 100.0 if totals['planned'] else 0.0
        )

    @classmethod
    def _add_totals(cls, target, source):
        target['planned'] += source['planned']
        target['actual'] += source['actual']
        target['available'] += source['available']
        target['execution'] = (
            target['actual'] / target['planned'] * 100.0 if target['planned'] else 0.0
        )

    @api.model
    def _prepare_comparison(self, wizard):
        """Solo sumar líneas legibles por el usuario (sin sudo ni búsqueda de gastos extra)."""
        domain = [
            ('company_id', '=', wizard.company_id.id),
            ('budget_id.year', '=', int(wizard.year)),
        ]
        if wizard.category_id:
            # Incluir TODAS las cuentas controladas del rubro seleccionado,
            # incluso si el valor relacionado almacenado en líneas antiguas
            # aún no está actualizado. Solo se buscan sus líneas del año.
            accounts = self.env['expense.budget.account'].with_context(
                active_test=False
            ).search([
                ('company_id', '=', wizard.company_id.id),
                ('category_id', '=', wizard.category_id.id),
            ])
            domain.append(('account_id', 'in', accounts.ids))
        # El nuevo selector acepta varias cuentas; el campo account_id se
        # conserva únicamente para compatibilidad con llamadas anteriores.
        selected_accounts = wizard.account_ids | wizard.account_id
        if selected_accounts:
            domain.append(('account_id', 'in', selected_accounts.ids))

        # Las reglas del modelo impiden incluir borradores cuando imprime el aprobador.
        lines = self.env['expense.budget.line'].search(domain)
        category_map = {}
        grand_total = self._empty_totals()
        month_labels = dict(self.env['expense.budget.line']._fields['month'].selection)
        for line in lines:
            account = line.account_id
            category = account.category_id
            if category.id not in category_map:
                category_map[category.id] = {
                    'category': category,
                    'accounts_map': {},
                    'line_count': 0,
                    'total': self._empty_totals(),
                }
            group = category_map[category.id]
            if account.id not in group['accounts_map']:
                group['accounts_map'][account.id] = {
                    'account': account,
                    'lines': [],
                    'line_count': 0,
                    'total': self._empty_totals(),
                }
            account_group = group['accounts_map'][account.id]
            account_group['lines'].append({
                'line': line,
                'month_name': month_labels.get(line.month, line.month),
            })
            account_group['line_count'] += 1
            group['line_count'] += 1
            self._add_line(account_group['total'], line)

        categories = []
        for group in sorted(category_map.values(), key=lambda item: (
                item['category'].code or '', item['category'].name or '', item['category'].id)):
            group['accounts'] = sorted(group.pop('accounts_map').values(), key=lambda item: (
                item['account'].code or '', item['account'].name or '', item['account'].id))
            for account in group['accounts']:
                # Mostrar las líneas del comparativo dentro de su cuenta, por mes.
                account['lines'].sort(key=lambda item: (
                    int(item['line'].month),
                    item['line'].budget_id.name or '',
                    item['line'].id,
                ))
                self._add_totals(group['total'], account['total'])
            self._add_totals(grand_total, group['total'])
            categories.append(group)

        return {
            'wizard': wizard,
            # Rubro sin cuentas explícitas: imprimir únicamente sus totales.
            'summary_by_category_only': bool(wizard.category_id and not selected_accounts),
            'selected_accounts': selected_accounts,
            'categories': categories,
            'grand_total': grand_total,
            'line_count': len(lines),
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
