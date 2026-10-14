# -*- coding: utf-8 -*-
"""Datos del PDF anual: rubros > cuentas > meses (sin modificar importaciones)."""

from odoo import api, models


MONTH_NAMES = (
    'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
    'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre',
)


class ReportAnnualExpenseBudget(models.AbstractModel):
    _name = 'report.expense_budget_control.report_annual_budget_document'
    _description = 'Informe PDF del presupuesto anual de gastos'

    @staticmethod
    def _empty_month():
        return {'planned': 0.0, 'actual': 0.0, 'available': 0.0, 'execution': 0.0, 'has_line': False}

    @classmethod
    def _empty_year(cls):
        return {str(month): cls._empty_month() for month in range(1, 13)}

    @staticmethod
    def _percentage(planned, actual):
        return actual / planned * 100.0 if planned else 0.0

    @classmethod
    def _add_amounts(cls, target, source):
        target['planned'] += source['planned']
        target['actual'] += source['actual']
        target['available'] += source['available']
        target['has_line'] = target['has_line'] or source['has_line']
        target['execution'] = cls._percentage(target['planned'], target['actual'])

    @classmethod
    def _annual_from_months(cls, monthly_data):
        """Porcentaje anual ponderado: consumo total / presupuesto total."""
        annual = cls._empty_month()
        for cell in monthly_data.values():
            if cell['has_line']:
                cls._add_amounts(annual, cell)
        return annual

    @api.model
    def _prepare_budget(self, budget):
        """Conservar el informe anual existente de un presupuesto individual."""
        return self._prepare_lines(budget.line_ids, budget, budget.name)

    @api.model
    def _prepare_lines(self, lines, source, budget_name):
        """Preparar el mismo formato anual con líneas de uno o varios presupuestos.

        La búsqueda de líneas del asistente se realiza sin sudo, respetando
        las reglas multiempresa y de visibilidad del aprobador.
        """
        categories = {}
        grand_totals = self._empty_year()
        for line in lines:
            category = line.category_id
            account = line.account_id
            if category.id not in categories:
                categories[category.id] = {
                    'category': category,
                    'accounts_by_id': {},
                    'months': self._empty_year(),
                }
            group = categories[category.id]
            if account.id not in group['accounts_by_id']:
                group['accounts_by_id'][account.id] = {
                    'account': account,
                    'months': self._empty_year(),
                }
            month = group['accounts_by_id'][account.id]['months'][line.month]
            month['planned'] += line.planned_amount
            month['actual'] += line.actual_amount
            month['available'] += line.variance_amount
            month['execution'] = line.execution_percentage
            month['has_line'] = True

        # Recalcular los subtotales sobre las líneas del presupuesto, incluso
        # cuando existan importes cero o movimientos de devolución (negativos).
        result_categories = []
        ordered_categories = sorted(categories.values(), key=lambda group: (
            group['category'].code or '', group['category'].name or '', group['category'].id,
        ))
        for group in ordered_categories:
            accounts = sorted(group.pop('accounts_by_id').values(), key=lambda item: (
                item['account'].code or '', item['account'].name or '', item['account'].id,
            ))
            group['accounts'] = accounts
            for account_data in accounts:
                account_data['annual'] = self._annual_from_months(account_data['months'])
                for month_number, source in account_data['months'].items():
                    if source['has_line']:
                        self._add_amounts(group['months'][month_number], source)
            for month_number, source in group['months'].items():
                if source['has_line']:
                    self._add_amounts(grand_totals[month_number], source)
            group['annual'] = self._annual_from_months(group['months'])
            result_categories.append(group)

        quarters = []
        for index in range(4):
            start = index * 3 + 1
            quarters.append({
                'number': index + 1,
                'months': [
                    {'number': str(month), 'name': MONTH_NAMES[month - 1]}
                    for month in range(start, start + 3)
                ],
            })
        return {
            'budget': source,
            'budget_name': budget_name,
            'categories': result_categories,
            'totals': grand_totals,
            'annual_total': self._annual_from_months(grand_totals),
            'months': [
                {'number': str(index), 'name': name}
                for index, name in enumerate(MONTH_NAMES, start=1)
            ],
            'quarters': quarters,
        }

    @api.model
    def _get_report_values(self, docids, data=None):
        budgets = self.env['expense.budget'].browse(docids).exists()
        # Mantener reglas de lectura y multiempresa; no utilizar sudo().
        budgets.check_access('read')
        return {
            'doc_ids': budgets.ids,
            'doc_model': 'expense.budget',
            'docs': budgets,
            'reports': [self._prepare_budget(budget) for budget in budgets],
        }


class ReportAnnualExpenseBudgetFromWizard(models.AbstractModel):
    _name = 'report.expense_budget_control.report_annual_budget_wizard_document'
    _description = 'Presupuesto anual desde el asistente Proyectado vs. real'

    @api.model
    def _prepare_wizard(self, wizard):
        domain = [
            ('company_id', '=', wizard.company_id.id),
            ('budget_id.year', '=', int(wizard.year)),
        ]
        if wizard.category_id:
            domain.append(('account_id.category_id', '=', wizard.category_id.id))
        selected_accounts = wizard.account_ids | wizard.account_id
        if selected_accounts:
            domain.append(('account_id', 'in', selected_accounts.ids))

        lines = self.env['expense.budget.line'].search(domain)
        title = wizard.category_id.name if wizard.category_id else 'Todos los presupuestos'
        return self.env['report.expense_budget_control.report_annual_budget_document']._prepare_lines(
            lines, wizard, title,
        )

    @api.model
    def _get_report_values(self, docids, data=None):
        wizards = self.env['expense.budget.comparison.report.wizard'].browse(docids).exists()
        wizards.check_access('read')
        return {
            'doc_ids': wizards.ids,
            'doc_model': 'expense.budget.comparison.report.wizard',
            'docs': wizards,
            'reports': [self._prepare_wizard(wizard) for wizard in wizards],
        }
