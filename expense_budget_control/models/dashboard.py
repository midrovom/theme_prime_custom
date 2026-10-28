# -*- coding: utf-8 -*-
"""Cifras agregadas para el dashboard, respetando ACL y reglas de empresa/estado."""
from collections import defaultdict
from odoo import _, api, fields, models
from odoo.exceptions import AccessError, ValidationError
from .amount_utils import exact_sum


MONTH_LABELS = (
    'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
    'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre',
)


class ExpenseBudgetDashboard(models.AbstractModel):
    _name = 'expense.budget.dashboard'
    _description = 'Datos del dashboard de gastos'

    @api.model
    def get_mobile_navigation(self):
        """Mobile home entries filtered by exactly the existing module roles.

        It intentionally returns actions, not model records, and it never sudoes
        or grants additional menu/model access to the current user.
        """
        user = self.env.user
        has = lambda group: user.has_group('expense_budget_control.' + group)
        read = has('group_expense_budget_user')
        register = has('group_expense_budget_registrar')
        approve = has('group_expense_budget_approver')
        manage = has('group_expense_budget_manager')
        if not (read or register or approve or manage):
            raise AccessError(_('No tiene permiso para consultar Control de Gastos.'))

        options = [
            ('Presupuestos', 'Crear y consultar presupuestos',
             'fa-file-text-o', 'action_expense_budget', read or register or manage,
             'expense.budget'),
            ('Aprobación de presupuestos', 'Pendientes, aprobados y rechazados',
             'fa-check-square-o', 'action_expense_budget_approval', approve or manage,
             'expense.budget'),
            ('Dashboard de gastos', 'Gráficos por mes, rubro y cuenta',
             'fa-pie-chart', 'action_expense_budget_dashboard', read or approve or manage,
             None),
            ('Proyectado vs. real', 'Comparación e impresión PDF',
             'fa-bar-chart', 'action_expense_budget_comparison', read or approve or manage,
             'expense.budget.line'),
            ('Gastos reales', 'Movimientos consumidos',
             'fa-money', 'action_expense_budget_expense', read or approve or manage,
             'expense.budget.expense'),
            ('Importar Excel / CSV', 'Cargar líneas desde archivo',
             'fa-upload', 'action_expense_budget_import', register or manage,
             'expense.budget.import.wizard'),
            ('Cuentas controladas', 'Administrar cuentas',
             'fa-list-alt', 'action_expense_budget_account', manage,
             'expense.budget.account'),
            ('Centros de costo', 'Catálogo de centros por empresa',
             'fa-building-o', 'action_expense_budget_cost_center', manage,
             'expense.budget.cost.center'),
            ('Configuración API ERP', 'Tres conexiones: cuentas, centros y consumos',
             'fa-cogs', 'action_expense_budget_api_administrator', manage,
             'expense.budget.api.config'),
            ('Historial API', 'Resultados de sincronización',
             'fa-history', 'action_expense_budget_sync_log', manage,
             'expense.budget.sync.log'),
        ]
        configuration_actions = {
            'action_expense_budget_expense', 'action_expense_budget_category',
            'action_expense_budget_account', 'action_expense_budget_cost_center',
            'action_expense_budget_api_administrator', 'action_expense_budget_sync_log',
        }
        sections = []
        for title, subtitle, icon, external_id, visible, model in options:
            if not visible:
                continue
            if model and not self.env[model].check_access_rights('read', raise_exception=False):
                continue
            action = self.env.ref('expense_budget_control.' + external_id, raise_if_not_found=False)
            if action:
                sections.append({
                    'id': action.id, 'title': title, 'subtitle': subtitle, 'icon': icon,
                    'configuration': external_id in configuration_actions,
                })
        return sections

    @api.model
    def get_dashboard_data(self, company_id=False, year=False, cost_center_id=False):
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
                    'year': False, 'accounts': [], 'categories': [], 'cost_centers': [],
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
        centers = self.env['expense.budget.cost.center'].search([
            ('company_id', '=', company.id),
        ], order='name')
        chosen_center = int(cost_center_id) if cost_center_id else False
        if chosen_center and chosen_center not in centers.ids:
            raise AccessError(_('El centro de costo no pertenece a la empresa seleccionada.'))
        if chosen_center:
            lines = lines.filtered(lambda line: line.cost_center_id.id == chosen_center)
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
            month_index = int(line.month) - 1
            totals[account.id][month_index] = exact_sum((totals[account.id][month_index], line.actual_amount))

        return {
            'companies': companies_data,
            'company_id': company.id,
            'years': years,
            'year': selected_year,
            'currency': company.currency_id.symbol or company.currency_id.name,
            'decimal_digits': self.env['decimal.precision'].precision_get('Presupuesto de Gastos'),
            'month_names': list(MONTH_LABELS),
            'categories': sorted(categories.values(), key=lambda c: (c['name'], c['id'])),
            'cost_centers': [{'id': cc.id, 'name': cc.name} for cc in centers],
            'cost_center_id': chosen_center,
            'accounts': [dict(account, months=totals[account['id']])
                         for account in sorted(accounts.values(), key=lambda a: (a['name'], a['id']))],
        }
