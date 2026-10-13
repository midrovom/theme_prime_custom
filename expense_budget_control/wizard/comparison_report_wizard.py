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
    year = fields.Integer(
        string='Año', required=True,
        default=lambda self: fields.Date.context_today(self).year,
    )
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
        if self.account_id and self.category_id and self.account_id.category_id != self.category_id:
            self.account_id = False

    @api.constrains('year', 'company_id', 'category_id', 'account_id')
    def _check_filters(self):
        for wizard in self:
            if not 1900 <= wizard.year <= 2100:
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
