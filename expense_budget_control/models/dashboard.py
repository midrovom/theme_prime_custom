# -*- coding: utf-8 -*-
"""Cifras agregadas para el dashboard, respetando ACL y reglas de empresa/estado."""
from collections import defaultdict
from odoo import _, api, fields, models
from odoo.exceptions import AccessError, ValidationError


MONTH_LABELS = (
    'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
    'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre',
)


class ExpenseBudgetDashboard(models.AbstractModel):
    _name = 'expense.budget.dashboard'
    _description = 'Datos del dashboard de gastos'

    @api.model
    def get_dashboard_data(self, company_id=False, year=False):
        """Los gastos provienen del consumo calculado de las proyecciones mensuales.

        Se busca sin sudo para excluir borradores a los aprobadores y respetar
        las restricciones multiempresa ya configuradas en la aplicación.
        """
        if not any(self.env.user.has_group('expense_budget_control.' + group)
                   for group in ('group_expense_budget_user',
                                 'group_expense_budget_approver',
                                 'group_expense_budget_manager')):
            raise AccessError(_('No tiene permiso para consultar el dashboard de gastos.'))

        companies = self.env['res.company'].search([], order='name')
        companies_data = [{'id': c.id, 'name': c.name} for c in companies]
        if not companies:
            return {'companies': [], 'company_id': False, 'years': [],
                    'year': False, 'accounts': [], 'categories': [],
                    'month_names': list(MONTH_LABELS), 'currency': ''}

        chosen_id = int(company_id) if company_id else self.env.company.id
        company = companies.filtered(lambda c: c.id == chosen_id)[:1]
        if not company:
            raise AccessError(_('La empresa seleccionada no está disponible.'))

        budgets = self.env['expense.budget'].search([
            ('company_id', '=', company.id),
        ])
        years = sorted({b.year for b in budgets}, reverse=True)
        current_year = fields.Date.context_today(self).year
        selected_year = int(year) if year else (current_year if current_year in years or not years else years[0])
        if selected_year < 2000 or selected_year > 2100:
            raise ValidationError(_('Seleccione un año válido.'))
        if selected_year not in years:
            years = sorted(set(years) | {selected_year}, reverse=True)

        # La búsqueda de líneas, igual que el informe PDF, aplica reglas de
        # acceso de expense.budget.line (incluido el filtro del aprobador).
        lines = self.env['expense.budget.line'].search([
            ('company_id', '=', company.id),
            ('budget_id.year', '=', selected_year),
        ])
        totals = defaultdict(lambda: [0.0] * 12)
        categories = {}
        accounts = {}
        for line in lines:
            account = line.account_id
            category = account.category_id or line.category_id
            category_id = category.id or 0
            categories[category_id] = {
                'id': category_id,
                'name': category.name if category else _('Sin rubro'),
            }
            accounts[account.id] = {
                'id': account.id,
                'name': account.name,
                'category_id': category_id,
            }
            totals[account.id][int(line.month) - 1] += line.actual_amount

        return {
            'companies': companies_data,
            'company_id': company.id,
            'years': years,
            'year': selected_year,
            'currency': company.currency_id.symbol or company.currency_id.name,
            'month_names': list(MONTH_LABELS),
            'categories': sorted(categories.values(), key=lambda c: (c['name'], c['id'])),
            'accounts': [dict(account, months=[round(v, 2) for v in totals[account['id']]])
                         for account in sorted(accounts.values(), key=lambda a: (a['name'], a['id']))],
        }
