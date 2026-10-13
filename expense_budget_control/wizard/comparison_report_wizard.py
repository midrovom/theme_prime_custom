# -*- coding: utf-8 -*-
"""Parámetros para imprimir Proyectado vs. real, sin cambiar presupuestos."""

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


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
    account_id = fields.Many2one(
        'expense.budget.account', string='Cuenta controlada',
        domain="[('company_id', '=', company_id)]",
    )

    @api.onchange('company_id')
    def _onchange_company_id(self):
        self.category_id = False
        self.account_id = False

    @api.onchange('category_id')
    def _onchange_category_id(self):
        # Al seleccionar únicamente Rubro no conservar una cuenta de un
        # filtro anterior (ni siquiera si pertenece al mismo rubro).
        # Dejar la cuenta vacía significa imprimirlas todas.
        self.account_id = False

    @api.constrains('year', 'company_id', 'category_id', 'account_id')
    def _check_filters(self):
        for wizard in self:
            if not 1900 <= int(wizard.year) <= 2100:
                raise ValidationError(_('Seleccione un año válido entre 1900 y 2100.'))
            if wizard.category_id and wizard.category_id.company_id != wizard.company_id:
                raise ValidationError(_('El rubro no pertenece a la empresa seleccionada.'))
            if wizard.account_id and wizard.account_id.company_id != wizard.company_id:
                raise ValidationError(_('La cuenta no pertenece a la empresa seleccionada.'))
            if (wizard.category_id and wizard.account_id and
                    wizard.account_id.category_id != wizard.category_id):
                raise ValidationError(_('La cuenta no pertenece al rubro seleccionado.'))

    def action_print_pdf(self):
        self.ensure_one()
        self.check_access('read')
        return self.env.ref(
            'expense_budget_control.action_report_expense_budget_comparison'
        ).report_action(self)
