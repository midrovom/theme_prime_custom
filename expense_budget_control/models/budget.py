# -*- coding: utf-8 -*-
from datetime import date

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError


MONTHS = [(str(index), name) for index, name in enumerate((
    'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
    'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre',
), start=1)]


class ExpenseBudgetCategory(models.Model):
    _name = 'expense.budget.category'
    _description = 'Rubro presupuestario de gastos'
    _order = 'code, name'
    _rec_name = 'name'
    _check_company_auto = True

    code = fields.Char(string='Código de rubro', required=True, index=True)
    name = fields.Char(string='Rubro', required=True)
    company_id = fields.Many2one('res.company', string='Empresa', required=True,
                                 default=lambda self: self.env.company, index=True)
    active = fields.Boolean(default=True)
    account_ids = fields.One2many('expense.budget.account', 'category_id', string='Cuentas')

    _sql_constraints = [
        ('category_company_code_unique', 'unique(company_id, code)',
         'El código del rubro ya existe para esta empresa.'),
    ]

    def name_get(self):
        return [(rec.id, '%s - %s' % (rec.code, rec.name)) for rec in self]


class ExpenseBudgetAccount(models.Model):
    _name = 'expense.budget.account'
    _description = 'Cuenta de gasto controlada'
    _order = 'code, name'
    _check_company_auto = True

    code = fields.Char(string='Código de cuenta', required=True, index=True)
    name = fields.Char(string='Cuenta de gasto', required=True)
    category_id = fields.Many2one('expense.budget.category', string='Rubro', required=True,
                                  ondelete='restrict', check_company=True)
    company_id = fields.Many2one('res.company', string='Empresa', required=True,
                                 default=lambda self: self.env.company, index=True)
    active = fields.Boolean(default=True)
    note = fields.Text(string='Observaciones')

    _sql_constraints = [
        ('account_company_code_unique', 'unique(company_id, code)',
         'El código de cuenta ya existe para esta empresa.'),
    ]

    @api.constrains('company_id', 'category_id')
    def _check_category_company(self):
        for rec in self:
            if rec.category_id and rec.category_id.company_id != rec.company_id:
                raise ValidationError(_('El rubro debe pertenecer a la misma empresa que la cuenta.'))

    def name_get(self):
        return [(rec.id, '%s - %s' % (rec.code, rec.name)) for rec in self]


class ExpenseBudget(models.Model):
    _name = 'expense.budget'
    _description = 'Presupuesto anual de gastos'
    _order = 'year desc, id desc'
    _check_company_auto = True

    name = fields.Char(string='Presupuesto', required=True)
    year = fields.Integer(string='Año', required=True,
                          default=lambda self: fields.Date.context_today(self).year, index=True)
    company_id = fields.Many2one('res.company', string='Empresa', required=True,
                                 default=lambda self: self.env.company, index=True)
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id', store=True)
    state = fields.Selection([
        ('draft', 'Borrador'), ('approved', 'Aprobado'), ('closed', 'Cerrado'),
    ], default='draft', required=True, string='Estado')
    line_ids = fields.One2many('expense.budget.line', 'budget_id', string='Proyecciones mensuales')
    planned_amount = fields.Monetary(string='Total proyectado', compute='_compute_totals',
                                     store=True, currency_field='currency_id')
    actual_amount = fields.Monetary(string='Total consumido', compute='_compute_totals',
                                    store=True, currency_field='currency_id')
    variance_amount = fields.Monetary(string='Saldo disponible', compute='_compute_totals',
                                      store=True, currency_field='currency_id')
    execution_percentage = fields.Float(string='Ejecución (%)', compute='_compute_totals',
                                        store=True, digits=(16, 2))
    note = fields.Text(string='Observaciones')

    _sql_constraints = [
        ('year_company_unique', 'unique(company_id, year)',
         'Ya existe un presupuesto anual para esta empresa y año.'),
    ]

    @api.depends('line_ids.planned_amount', 'line_ids.actual_amount')
    def _compute_totals(self):
        for rec in self:
            rec.planned_amount = sum(rec.line_ids.mapped('planned_amount'))
            rec.actual_amount = sum(rec.line_ids.mapped('actual_amount'))
            rec.variance_amount = rec.planned_amount - rec.actual_amount
            rec.execution_percentage = (rec.actual_amount / rec.planned_amount * 100.0
                                        if rec.planned_amount else 0.0)

    @api.constrains('year')
    def _check_year(self):
        for rec in self:
            if not 2000 <= rec.year <= 2100:
                raise ValidationError(_('El año debe estar entre 2000 y 2100.'))

    def write(self, vals):
        if ('year' in vals or 'company_id' in vals) and any(
            rec.state != 'draft' or rec.line_ids for rec in self
        ):
            raise UserError(_('No puede cambiar el año o la empresa de un presupuesto con líneas o aprobado.'))
        return super().write(vals)

    def action_approve(self):
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_('Solo puede aprobar presupuestos en borrador.'))
            if not rec.line_ids:
                raise UserError(_('Debe cargar al menos una línea presupuestaria.'))
            rec.state = 'approved'

    def action_close(self):
        for rec in self:
            if rec.state != 'approved':
                raise UserError(_('Solo puede cerrar presupuestos aprobados.'))
            rec.state = 'closed'

    def action_reopen(self):
        self.write({'state': 'draft'})

    def action_reconcile_expenses(self):
        if not self.env.user.has_group('expense_budget_control.group_expense_budget_manager'):
            raise AccessError(_('No tiene permiso para conciliar gastos.'))
        reconciled = 0
        for budget in self:
            index = {(line.account_id.id, line.month): line for line in budget.line_ids}
            expenses = self.env['expense.budget.expense'].search([
                ('company_id', '=', budget.company_id.id),
                ('date', '>=', '%04d-01-01' % budget.year),
                ('date', '<=', '%04d-12-31' % budget.year),
                ('budget_line_id', '=', False),
            ])
            for expense in expenses:
                line = index.get((expense.account_id.id, str(expense.date.month)))
                if line:
                    expense.write({'budget_line_id': line.id})
                    reconciled += 1
        return {'type': 'ir.actions.client', 'tag': 'display_notification', 'params': {
            'title': _('Conciliación completada'),
            'message': _('%s gastos asignados a sus líneas presupuestarias.') % reconciled,
            'type': 'success', 'sticky': False,
        }}

    @api.model
    def cron_sync_all(self):
        """Cron técnico: el usuario de la tarea debe ser administrador del sistema."""
        if not (self.env.is_superuser() or self.env.user.has_group('base.group_system')):
            raise AccessError(_('Solo el administrador del sistema puede ejecutar la tarea API.'))
        return self.env['expense.budget.api.sync'].cron_sync_all()

    def action_sync_api(self):
        if not self.env.user.has_group('expense_budget_control.group_expense_budget_manager'):
            raise AccessError(_('No tiene permisos para sincronizar gastos.'))
        self.ensure_one()
        result = self.env['expense.budget.api.sync']._sync_company(self.company_id)
        return self.env['expense.budget.api.sync']._notification(result)


class ExpenseBudgetLine(models.Model):
    _name = 'expense.budget.line'
    _description = 'Presupuesto mensual por cuenta'
    _order = 'budget_id, month, account_id'
    _check_company_auto = True

    budget_id = fields.Many2one('expense.budget', string='Presupuesto', required=True,
                                ondelete='cascade', check_company=True, index=True)
    company_id = fields.Many2one('res.company', related='budget_id.company_id',
                                 store=True, index=True)
    currency_id = fields.Many2one('res.currency', related='budget_id.currency_id', store=True)
    account_id = fields.Many2one('expense.budget.account', string='Cuenta controlada',
                                 required=True, ondelete='restrict', check_company=True)
    category_id = fields.Many2one('expense.budget.category', related='account_id.category_id',
                                  store=True, string='Rubro', index=True)
    month = fields.Selection(MONTHS, string='Mes', required=True, index=True)
    planned_amount = fields.Monetary(string='Proyectado', required=True, default=0,
                                     currency_field='currency_id')
    expense_ids = fields.One2many('expense.budget.expense', 'budget_line_id', string='Gastos reales')
    actual_amount = fields.Monetary(string='Consumido', compute='_compute_amounts',
                                    store=True, currency_field='currency_id')
    variance_amount = fields.Monetary(string='Disponible', compute='_compute_amounts',
                                      store=True, currency_field='currency_id')
    execution_percentage = fields.Float(string='Ejecución (%)', compute='_compute_amounts',
                                        store=True, digits=(16, 2))

    _sql_constraints = [
        ('budget_month_account_unique', 'unique(budget_id, account_id, month)',
         'Solo puede existir una proyección para cada cuenta y mes del presupuesto.'),
        ('planned_amount_nonnegative', 'check(planned_amount >= 0)',
         'La proyección no puede ser negativa.'),
    ]

    @api.depends('planned_amount', 'expense_ids.amount')
    def _compute_amounts(self):
        for rec in self:
            rec.actual_amount = sum(rec.expense_ids.mapped('amount'))
            rec.variance_amount = rec.planned_amount - rec.actual_amount
            rec.execution_percentage = (rec.actual_amount / rec.planned_amount * 100.0
                                        if rec.planned_amount else 0.0)

    @api.constrains('account_id', 'budget_id')
    def _check_account_company(self):
        for rec in self:
            if rec.account_id.company_id != rec.budget_id.company_id:
                raise ValidationError(_('La cuenta debe pertenecer a la empresa del presupuesto.'))

    @api.model_create_multi
    def create(self, vals_list):
        budgets = self.env['expense.budget']
        for vals in vals_list:
            budget = budgets.browse(vals.get('budget_id'))
            if budget.exists() and budget.state != 'draft':
                raise UserError(_('Solo puede modificar proyecciones en presupuestos borrador.'))
        records = super().create(vals_list)
        records._assign_unmatched_expenses()
        return records

    def write(self, vals):
        protected = {'account_id', 'budget_id', 'month', 'planned_amount'}
        if protected.intersection(vals) and any(rec.budget_id.state != 'draft' for rec in self):
            raise UserError(_('No puede cambiar proyecciones de presupuestos aprobados o cerrados.'))
        if {'account_id', 'budget_id', 'month'}.intersection(vals) and any(rec.expense_ids for rec in self):
            raise UserError(_('No puede cambiar cuenta, mes o presupuesto de una línea con gastos reales. '
                              'Puede modificar el monto proyectado o volver a conciliar los movimientos.'))
        result = super().write(vals)
        if {'account_id', 'budget_id', 'month'}.intersection(vals):
            self._assign_unmatched_expenses()
        return result

    def unlink(self):
        if any(rec.budget_id.state != 'draft' for rec in self):
            raise UserError(_('Solo puede eliminar líneas de presupuestos borrador.'))
        return super().unlink()

    def _assign_unmatched_expenses(self):
        Expense = self.env['expense.budget.expense']
        for line in self:
            year, month = line.budget_id.year, int(line.month)
            start = date(year, month, 1)
            end = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
            Expense.search([
                ('company_id', '=', line.company_id.id),
                ('account_id', '=', line.account_id.id),
                ('date', '>=', fields.Date.to_string(start)),
                ('date', '<', fields.Date.to_string(end)),
                ('budget_line_id', '=', False),
            ]).write({'budget_line_id': line.id})
