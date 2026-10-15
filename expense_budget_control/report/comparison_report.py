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
        # Evitar usar una variación almacenada desactualizada: disponible
        # es siempre presupuesto proyectado de la línea menos su consumo.
        available = line.planned_amount - line.actual_amount
        target['total']['available'] += available
        # Conservar el criterio de ejecución de la vista agrupada existente.
        target['total']['execution'] += line.execution_percentage
        month = target['monthly'][int(line.month)]
        month['planned'] += line.planned_amount
        month['actual'] += line.actual_amount
        month['available'] += available

    @classmethod
    def _add_summary(cls, target, source):
        for key in ('planned', 'actual', 'available', 'execution'):
            target['total'][key] += source['total'][key]
        for m in range(1, 13):
            for key in ('planned', 'actual', 'available'):
                target['monthly'][m][key] += source['monthly'][m][key]

    @staticmethod
    def _finish_row(row, month_numbers):
        """Sumar el proyectado inicial y los proyectados del período consultado.

        El inicial es el proyectado del mes inmediatamente anterior al primero
        seleccionado (cero si comienza en enero). Solo los meses seleccionados
        aportan nuevos proyectados y consumidos al saldo final.
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
        # El inicial es el PROYECTADO del mes previo, no la suma de saldos
        # disponibles ni un importe de consumo de meses anteriores.
        openings = {
            number: (row['monthly'][number - 1]['planned'] if number > 1 else 0.0)
            for number in range(1, 13)
        }

        first_month = selected_months[0]
        opening = openings[first_month]
        projected = sum(row['monthly'][month]['planned'] for month in selected_months)
        consumed = sum(row['monthly'][month]['actual'] for month in selected_months)
        period_closings = {
            first_month: {
                'saldo_actual': consumed,
                'saldo_disponible': opening + projected - consumed,
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
        # Si no hay selección, imprimir enero-diciembre sin preseleccionarlos
        # en el asistente. Consultar sin sudo: las ACL del catálogo siguen activas.
        selected_months = wizard.month_ids or self.env[
            'expense.budget.comparison.month'
        ].search([], order='number')
        selected_months = sorted(selected_months, key=lambda record: record.number)
        numbers = [m.number for m in selected_months]
        if not numbers:
            from odoo.exceptions import ValidationError
            from odoo import _
            raise ValidationError(_('No se encontraron meses configurados para imprimir.'))

        domain = [
            ('company_id', '=', wizard.company_id.id),
            ('budget_id.year', '=', int(wizard.year)),
        ]
        if wizard.category_id:
            # Usar el rubro de la línea o el de su cuenta, sin una búsqueda
            # intermedia del catálogo que pueda excluir líneas históricas.
            domain.extend([
                '|',
                ('account_id.category_id', '=', wizard.category_id.id),
                ('category_id', '=', wizard.category_id.id),
            ])
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
            category = wizard.category_id if wizard.category_id else (account.category_id or line.category_id)
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

        # Con solo un rubro seleccionado, incluir TODAS sus cuentas visibles
        # para la empresa, aunque alguna todavía no tenga proyecciones ese año.
        # La búsqueda respeta las reglas de acceso del usuario (sin sudo).
        if wizard.category_id and not selected_accounts:
            group = category_map.setdefault(wizard.category_id.id, {
                'category': wizard.category_id, 'accounts_map': {}, 'line_count': 0,
                'total': self._empty_totals(), 'monthly': self._empty_months(),
            })
            category_accounts = self.env['expense.budget.account'].search([
                ('company_id', '=', wizard.company_id.id),
                ('category_id', '=', wizard.category_id.id),
            ])
            for account in category_accounts:
                group['accounts_map'].setdefault(account.id, {
                    'account': account, 'lines': [], 'budgets_map': {}, 'line_count': 0,
                    'total': self._empty_totals(), 'monthly': self._empty_months(),
                })

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
            # Se conserva el indicador legado; el PDF ahora detalla las cuentas
            # incluso cuando se selecciona únicamente el rubro.
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
