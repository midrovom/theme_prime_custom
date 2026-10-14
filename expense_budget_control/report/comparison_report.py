# -*- coding: utf-8 -*-
"""Comparativo mensual por rubro, cuenta y presupuesto con saldos acumulados."""
from odoo import api, models


class ReportExpenseBudgetComparison(models.AbstractModel):
    _name = 'report.expense_budget_control.report_comparison_document'
    _description = 'Reporte mensual Proyectado vs. real por rubro y cuenta'

    @staticmethod
    def _empty_totals():
        return {'planned': 0.0, 'actual': 0.0, 'available': 0.0, 'execution': 0.0}

    @staticmethod
    def _empty_months():
        return {m: {'planned': 0.0, 'actual': 0.0, 'available': 0.0}
                for m in range(1, 13)}

    @classmethod
    def _add_line(cls, target, line):
        target['total']['planned'] += line.planned_amount
        target['total']['actual'] += line.actual_amount
        target['total']['available'] += line.variance_amount
        # Conservar el criterio de ejecución de la vista agrupada existente.
        target['total']['execution'] += line.execution_percentage
        month = target['monthly'][int(line.month)]
        month['planned'] += line.planned_amount
        month['actual'] += line.actual_amount
        month['available'] += line.variance_amount

    @classmethod
    def _add_summary(cls, target, source):
        for key in ('planned', 'actual', 'available', 'execution'):
            target['total'][key] += source['total'][key]
        for m in range(1, 13):
            for key in ('planned', 'actual', 'available'):
                target['monthly'][m][key] += source['monthly'][m][key]

    @staticmethod
    def _finish_row(row, month_numbers):
        """Saldo inicial del período anterior y consumos de los meses elegidos.

        Todos los meses elegidos se representan en un único bloque continuo:
        - Inicial: disponible acumulado hasta el mes anterior al primero.
        - Actual: consumo solo de los meses seleccionados.
        - Disponible final: inicial menos actual (sin añadir proyecciones).
        """
        selected_months = sorted(set(month_numbers))
        cells = {
            number: {
                'planned': row['monthly'][number]['planned'],
                'actual': row['monthly'][number]['actual'],
                'available': row['monthly'][number]['available'],
            }
            for number in selected_months
        }
        # Meses previos de calendario, aunque no formen parte de la selección.
        openings = {}
        prior_available = 0.0
        for number in range(1, 13):
            openings[number] = prior_available
            prior_available += row['monthly'][number]['available']

        # Un único cierre después del último mes seleccionado (sin subdivisión).
        first_month = selected_months[0]
        opening = openings[first_month]
        consumed = sum(row['monthly'][month]['actual'] for month in selected_months)
        period_closings = {
            first_month: {
                'saldo_actual': consumed,
                'saldo_disponible': opening - consumed,
            },
        }
        row['monthly_report'] = {
            'cells': cells,
            'openings': openings,
            'period_closings': period_closings,
        }

    @api.model
    def _prepare_comparison(self, wizard):
        """Respetar las reglas de empresa y estado; jamás elevar permisos."""
        selected_months = sorted(wizard.month_ids, key=lambda record: record.number)
        numbers = [m.number for m in selected_months]
        # La validación está también en el asistente (evita llamadas directas).
        if not numbers:
            from odoo.exceptions import ValidationError
            from odoo import _
            raise ValidationError(_('Seleccione al menos un mes para el reporte.'))

        domain = [
            ('company_id', '=', wizard.company_id.id),
            ('budget_id.year', '=', int(wizard.year)),
        ]
        if wizard.category_id:
            accounts = self.env['expense.budget.account'].with_context(
                active_test=False).search([
                    ('company_id', '=', wizard.company_id.id),
                    ('category_id', '=', wizard.category_id.id),
                ])
            domain.append(('account_id', 'in', accounts.ids))
        selected_accounts = wizard.account_ids | wizard.account_id
        if selected_accounts:
            domain.append(('account_id', 'in', selected_accounts.ids))

        # Consultar TODOS los meses para obtener el saldo anterior al primer mes.
        lines = self.env['expense.budget.line'].search(domain)
        category_map = {}
        grand_total = {'total': self._empty_totals(), 'monthly': self._empty_months()}
        month_labels = dict(self.env['expense.budget.line']._fields['month'].selection)
        for line in lines:
            account = line.account_id
            category = account.category_id
            group = category_map.setdefault(category.id, {
                'category': category, 'accounts_map': {}, 'line_count': 0,
                'total': self._empty_totals(), 'monthly': self._empty_months(),
            })
            account_group = group['accounts_map'].setdefault(account.id, {
                'account': account, 'lines': [], 'budgets_map': {}, 'line_count': 0,
                'total': self._empty_totals(), 'monthly': self._empty_months(),
            })
            account_group['lines'].append({
                'line': line, 'month_name': month_labels.get(line.month, line.month),
            })
            budget_row = account_group['budgets_map'].setdefault(line.budget_id.id, {
                'budget': line.budget_id, 'line_count': 0,
                'total': self._empty_totals(), 'monthly': self._empty_months(),
            })
            self._add_line(budget_row, line)
            budget_row['line_count'] += 1
            account_group['line_count'] += 1
            group['line_count'] += 1

        categories = []
        for group in sorted(category_map.values(), key=lambda item: (
                item['category'].code or '', item['category'].name or '', item['category'].id)):
            group['accounts'] = sorted(group.pop('accounts_map').values(), key=lambda item: (
                item['account'].code or '', item['account'].name or '', item['account'].id))
            for account in group['accounts']:
                account['lines'].sort(key=lambda item: (
                    int(item['line'].month), item['line'].budget_id.name or '', item['line'].id,
                ))
                account['budgets'] = sorted(account.pop('budgets_map').values(), key=lambda item: (
                    item['budget'].name or '', item['budget'].id,
                ))
                for budget_row in account['budgets']:
                    self._add_summary(account, budget_row)
                    self._finish_row(budget_row, numbers)
                self._finish_row(account, numbers)
                self._add_summary(group, account)
            self._finish_row(group, numbers)
            self._add_summary(grand_total, group)
            categories.append(group)
        self._finish_row(grand_total, numbers)

        # Todos los meses elegidos se dibujan juntos en la misma tabla.
        first_month = selected_months[0].number
        pages = [{
            'months': [{'number': m.number, 'name': m.name} for m in selected_months],
            'first_month': first_month,
            'opening': first_month > 1,
            'previous_month_name': month_labels.get(str(first_month - 1), ''),
            'number': 1,
        }]

        return {
            'wizard': wizard,
            'selected_accounts': selected_accounts,
            # Mantener modo anterior: solo rubro -> fila de total por rubro.
            'summary_by_category_only': bool(wizard.category_id and not selected_accounts),
            'categories': categories,
            'grand_total': grand_total['total'],
            'grand_row': grand_total,
            'line_count': len(lines),
            'pages': pages,
            'month_numbers': numbers,
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
