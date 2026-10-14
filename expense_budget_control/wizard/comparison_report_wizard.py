# -*- coding: utf-8 -*-
"""Parámetros para imprimir Proyectado vs. real, sin cambiar presupuestos."""

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ExpenseBudgetComparisonMonth(models.Model):
    """Catálogo fijo de meses disponible para la selección múltiple del informe."""
    _name = 'expense.budget.comparison.month'
    _description = 'Mes elegible en reportes comparativos'
    _order = 'number'

    name = fields.Char(required=True)
    number = fields.Integer(required=True, index=True)
    _sql_constraints = [
        ('comparison_month_unique', 'unique(number)', 'No se puede duplicar un mes.'),
    ]


class ExpenseBudgetComparisonReportWizard(models.TransientModel):
    _name = 'expense.budget.comparison.report.wizard'
    _description = 'Imprimir comparativo de presupuesto por rubro y cuenta'

    company_id = fields.Many2one(
        'res.company', string='Empresa', required=True,
        default=lambda self: self.env.company,
    )
    @api.model
    def _selection_years(self):
        """Años disponibles en presupuestos visibles para el usuario actual."""
        # Sin sudo: respetar las empresas y estados que permite ver su rol.
        years = set(self.env['expense.budget'].search([]).mapped('year'))
        years.add(fields.Date.context_today(self).year)
        return [(str(year), str(year)) for year in sorted(years, reverse=True)
                if 1900 <= year <= 2100]

    year = fields.Selection(
        selection='_selection_years', string='Año', required=True,
        default=lambda self: str(fields.Date.context_today(self).year),
    )

    month_ids = fields.Many2many(
        'expense.budget.comparison.month',
        'expense_budget_comparison_wizard_month_rel',
        'wizard_id', 'month_id', string='Meses del reporte',
        default=lambda self: self.env['expense.budget.comparison.month'].search([]),
        help='Seleccione los meses que se incluirán. Los saldos acumulados toman en cuenta los meses previos aunque no estén seleccionados.',
    )

    @api.model_create_multi
    def create(self, vals_list):
        # Conservar compatibilidad con llamadas anteriores que enviaban
        # el año numérico al asistente (cuando era fields.Integer).
        for vals in vals_list:
            if isinstance(vals.get('year'), int):
                vals['year'] = str(vals['year'])
        return super().create(vals_list)

    def write(self, vals):
        if isinstance(vals.get('year'), int):
            vals = dict(vals, year=str(vals['year']))
        return super().write(vals)

    category_id = fields.Many2one(
        'expense.budget.category', string='Rubro',
        domain="[('company_id', '=', company_id)]",
    )
    # Campo legado conservado para compatibilidad con asistentes transitorios
    # existentes y llamadas RPC previas; ya no aparece en la interfaz.
    account_id = fields.Many2one(
        'expense.budget.account', string='Cuenta controlada (legado)',
        domain="[('company_id', '=', company_id)]",
    )
    account_ids = fields.Many2many(
        'expense.budget.account',
        'expense_budget_comparison_wizard_account_rel',
        'wizard_id', 'account_id',
        string='Cuentas controladas',
    )

    @api.onchange('company_id')
    def _onchange_company_id(self):
        self.category_id = False
        self.account_id = False
        self.account_ids = [(5, 0, 0)]

    @api.onchange('category_id')
    def _onchange_category_id(self):
        # Al seleccionar únicamente Rubro no conservar una cuenta de un
        # filtro anterior (ni siquiera si pertenece al mismo rubro).
        # Dejar la cuenta vacía significa imprimirlas todas.
        self.account_id = False
        self.account_ids = [(5, 0, 0)]

    @api.constrains('year', 'company_id', 'category_id', 'account_id', 'account_ids', 'month_ids')
    def _check_filters(self):
        for wizard in self:
            if not wizard.month_ids:
                raise ValidationError(_('Seleccione al menos un mes para el reporte.'))
            if not 1900 <= int(wizard.year) <= 2100:
                raise ValidationError(_('Seleccione un año válido entre 1900 y 2100.'))
            if wizard.category_id and wizard.category_id.company_id != wizard.company_id:
                raise ValidationError(_('El rubro no pertenece a la empresa seleccionada.'))
            if wizard.account_id and wizard.account_id.company_id != wizard.company_id:
                raise ValidationError(_('La cuenta no pertenece a la empresa seleccionada.'))
            selected_accounts = wizard.account_ids | wizard.account_id
            if any(account.company_id != wizard.company_id for account in selected_accounts):
                raise ValidationError(_('Las cuentas deben pertenecer a la empresa seleccionada.'))
            if wizard.category_id and any(
                    account.category_id != wizard.category_id for account in selected_accounts):
                raise ValidationError(_('Todas las cuentas deben pertenecer al rubro seleccionado.'))

    def action_print_pdf(self):
        self.ensure_one()
        self.check_access('read')
        if not self.month_ids:
            raise ValidationError(_('Seleccione al menos un mes para el reporte.'))
        return self.env.ref(
            'expense_budget_control.action_report_expense_budget_comparison'
        ).report_action(self)
