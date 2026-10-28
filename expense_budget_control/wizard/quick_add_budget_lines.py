# -*- coding: utf-8 -*-
"""Asistente para crear varias proyecciones mensuales de una sola vez."""

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools.float_utils import float_compare, float_round
from ..models.budget import BUDGET_DECIMAL_PRECISION, budget_amount_digits


class ExpenseBudgetQuickAddWizard(models.TransientModel):
    _name = 'expense.budget.quick.add.wizard'
    _description = 'Agregar líneas presupuestarias por meses'

    budget_id = fields.Many2one('expense.budget', required=True, readonly=True, ondelete='cascade')
    company_id = fields.Many2one('res.company', related='budget_id.company_id', readonly=True)
    year = fields.Integer(related='budget_id.year', readonly=True)
    category_id = fields.Many2one('expense.budget.category', related='budget_id.category_id', readonly=True)
    currency_id = fields.Many2one('res.currency', related='budget_id.currency_id', readonly=True)

    account_id = fields.Many2one(
        'expense.budget.account', string='Cuenta controlada', required=True,
        domain="[('company_id', '=', company_id), ('category_id', '=', category_id)]",
    )
    cost_center_id = fields.Many2one(
        'expense.budget.cost.center', string='Centro de costo',
        domain="[('company_id', '=', company_id)]",
        help='La disponibilidad de meses se calcula independientemente para cada cuenta y centro de costo.',
    )
    month_ids = fields.Many2many(
        'expense.budget.comparison.month',
        'expense_budget_quick_add_month_rel', 'wizard_id', 'month_id',
        string='Meses a proyectar', required=True,
        help='Seleccione uno o varios meses. Solo aparecen meses disponibles para esta cuenta y centro de costo.',
    )
    available_month_ids = fields.Many2many(
        'expense.budget.comparison.month', compute='_compute_available_month_ids',
        string='Meses disponibles',
    )
    annual_amount = fields.Float(digits=BUDGET_DECIMAL_PRECISION, 
        string='Valor anual a distribuir', required=True,
        help='Importe total que se reparte entre los meses elegidos. Ejemplo: $1.200 entre enero, febrero y marzo = $400 por mes.',
    )
    target_locked = fields.Boolean(compute='_compute_allocation_preview')
    distribution_month_count = fields.Integer(
        string='Meses para distribuir', compute='_compute_allocation_preview',
    )
    monthly_amount = fields.Float(digits=BUDGET_DECIMAL_PRECISION, 
        string='Proyectado por mes',
        compute='_compute_allocation_preview',
    )
    allocation_note = fields.Char(compute='_compute_allocation_preview')

    def _pair_domain(self):
        self.ensure_one()
        return [
            ('company_id', '=', self.company_id.id),
            ('year', '=', self.year),
            ('account_id', '=', self.account_id.id),
            ('cost_center_id', '=', self.cost_center_id.id or False),
        ]

    def _find_target(self):
        self.ensure_one()
        if not (self.company_id and self.year and self.account_id):
            return self.env['expense.budget.annual.target']
        return self.env['expense.budget.annual.target'].sudo().search(
            self._pair_domain(), order='id desc', limit=1,
        )

    def _has_protected_lines(self):
        self.ensure_one()
        if not (self.company_id and self.year and self.account_id):
            return False
        return bool(self.env['expense.budget.line'].sudo().search_count(
            self._pair_domain() + [('approval_state', 'in', ('approved', 'to_approve'))]
        ))

    @api.depends('budget_id', 'account_id', 'cost_center_id', 'month_ids', 'annual_amount')
    def _compute_available_month_ids(self):
        Month = self.env['expense.budget.comparison.month'].sudo()
        Line = self.env['expense.budget.line'].sudo()
        months = Month.search([])
        for wizard in self:
            available = months
            if wizard.budget_id and wizard.account_id:
                used = Line.search(wizard._pair_domain() + [('month', '!=', False)])
                used_numbers = {int(line.month) for line in used if line.month}
                approved_through = Line._get_approved_through_month_for_pair_values(
                    wizard.company_id.id, wizard.year, wizard.account_id.id,
                    wizard.cost_center_id.id or False,
                )
                available = months.filtered(lambda item: (
                    item.number not in used_numbers
                    and (not approved_through or item.number > approved_through)
                ))
            wizard.available_month_ids = available

    @api.depends('budget_id', 'account_id', 'cost_center_id', 'month_ids', 'annual_amount')
    def _compute_allocation_preview(self):
        Line = self.env['expense.budget.line'].sudo()
        for wizard in self:
            target = wizard._find_target() if wizard.account_id and wizard.budget_id else self.env['expense.budget.annual.target']
            protected_lines = wizard._has_protected_lines() if wizard.account_id and wizard.budget_id else False
            locked = bool(target and (target._has_protected_months() or protected_lines))
            wizard.target_locked = locked
            if locked and target:
                count = target.distribution_month_count or 12
            elif not target and protected_lines:
                # Legacy approved months without a header target use the original /12 rule.
                count = Line._get_distribution_month_count_for_pair(
                    wizard.company_id.id, wizard.year, wizard.account_id.id,
                    wizard.cost_center_id.id or False,
                )
            elif wizard.account_id and wizard.budget_id:
                existing = Line.search(wizard._pair_domain() + [('approval_state', 'in', ('draft', 'rejected'))])
                month_numbers = {int(line.month) for line in existing if line.month}
                month_numbers.update(wizard.month_ids.mapped('number'))
                count = len(month_numbers) or len(wizard.month_ids) or 0
            else:
                count = len(wizard.month_ids) or 0
            wizard.distribution_month_count = count
            divisor = count if count > 0 else 1
            amount = wizard.annual_amount or 0.0
            raw_monthly = amount / divisor
            wizard.monthly_amount = float_round(raw_monthly, precision_digits=budget_amount_digits(self.env))
            if locked:
                wizard.allocation_note = _(
                    'Esta cuenta y centro ya tiene meses aprobados. Se conservará el importe anual y el prorrateo existente (%s meses); solo se añadirán meses que estén libres.'
                ) % count
            else:
                wizard.allocation_note = _(
                    'El valor se distribuirá entre %(count)s mes(es), incluyendo las proyecciones pendientes existentes para esta cuenta y centro.'
                ) % {'count': count}

    @api.onchange('account_id', 'cost_center_id')
    def _onchange_account_center(self):
        self.month_ids = [(5, 0, 0)]
        if not (self.budget_id and self.account_id):
            self.annual_amount = 0.0
            return
        target = self._find_target()
        if target:
            self.annual_amount = target.annual_amount
        else:
            self.annual_amount = self.env['expense.budget.line']._get_annual_amount_for_pair(
                self.company_id.id, self.year, self.account_id.id,
                self.cost_center_id.id or False,
            ) or 0.0

    @api.constrains('budget_id', 'account_id', 'cost_center_id', 'month_ids', 'annual_amount')
    def _check_wizard_values(self):
        for wizard in self:
            if wizard.annual_amount < 0:
                raise ValidationError(_('El valor anual no puede ser negativo.'))
            if wizard.budget_id and wizard.account_id:
                if wizard.account_id.company_id != wizard.company_id:
                    raise ValidationError(_('La cuenta controlada debe pertenecer a la empresa del presupuesto.'))
                if wizard.category_id and wizard.account_id.category_id != wizard.category_id:
                    raise ValidationError(_('La cuenta controlada debe pertenecer al rubro del presupuesto.'))
            if wizard.cost_center_id and wizard.cost_center_id.company_id != wizard.company_id:
                raise ValidationError(_('El centro de costo debe pertenecer a la empresa del presupuesto.'))

    def action_add_lines(self):
        self.ensure_one()
        budget = self.budget_id
        if not (self.env.user.has_group('expense_budget_control.group_expense_budget_registrar')
                or self.env.user.has_group('expense_budget_control.group_expense_budget_manager')):
            raise AccessError(_('No tiene permisos para agregar líneas al presupuesto.'))
        if budget.state != 'draft':
            raise UserError(_('Solo puede agregar líneas cuando el presupuesto está en borrador.'))
        if not self.account_id:
            raise UserError(_('Seleccione una cuenta controlada.'))
        if not self.month_ids:
            raise UserError(_('Seleccione al menos un mes para crear las líneas.'))
        if self.annual_amount <= 0:
            raise UserError(_('Ingrese un valor anual mayor que cero.'))
        if self.account_id.company_id != budget.company_id:
            raise ValidationError(_('La cuenta controlada debe pertenecer a la empresa del presupuesto.'))
        if budget.category_id and self.account_id.category_id != budget.category_id:
            raise ValidationError(_('La cuenta controlada debe pertenecer al rubro del presupuesto.'))
        if self.cost_center_id and self.cost_center_id.company_id != budget.company_id:
            raise ValidationError(_('El centro de costo debe pertenecer a la empresa del presupuesto.'))

        Line = self.env['expense.budget.line'].sudo()
        target_model = self.env['expense.budget.annual.target'].sudo()
        pair_domain = self._pair_domain()
        selected_numbers = sorted(set(self.month_ids.mapped('number')))
        if len(selected_numbers) != len(self.month_ids):
            raise ValidationError(_('No se puede seleccionar dos veces el mismo mes.'))

        # Re-check available months from the database, avoiding duplicate or old-period
        # lines even when the wizard is called through RPC rather than the UI.
        used_lines = Line.search(pair_domain + [('month', '!=', False)])
        used_numbers = {int(line.month) for line in used_lines if line.month}
        approved_through = Line._get_approved_through_month_for_pair_values(
            budget.company_id.id, budget.year, self.account_id.id,
            self.cost_center_id.id or False,
        )
        invalid = [n for n in selected_numbers if n in used_numbers or (approved_through and n <= approved_through)]
        if invalid:
            labels = ', '.join(self.env['expense.budget.comparison.month'].sudo().search(
                [('number', 'in', invalid)], order='number'
            ).mapped('name'))
            raise UserError(_(
                'Estos meses ya están presupuestados o no pueden reabrirse para la cuenta y centro seleccionados: %s. '
                'Seleccione únicamente meses disponibles.'
            ) % labels)

        target = target_model.search(pair_domain, order='id desc', limit=1)
        protected_lines = bool(Line.search_count(pair_domain + [('approval_state', 'in', ('approved', 'to_approve'))]))
        locked_target = bool(target and (target._has_protected_months() or protected_lines))
        amount = self.annual_amount
        if locked_target:
            if float_compare(amount, target.annual_amount, precision_digits=budget_amount_digits(self.env)) != 0:
                raise UserError(_(
                    'El presupuesto anual de esta cuenta y centro ya tiene meses aprobados. '
                    'Debe conservar el valor de %s para agregar los meses futuros.'
                ) % target.annual_amount)
            divisor = target.distribution_month_count or 12
        else:
            # While all projections are still editable, distribute the amount
            # over the union of selected and existing draft/rejected months.
            pending_lines = Line.search(pair_domain + [('approval_state', 'in', ('draft', 'rejected'))])
            all_month_numbers = {int(line.month) for line in pending_lines if line.month}
            all_month_numbers.update(selected_numbers)
            divisor = len(all_month_numbers) or len(selected_numbers)
            if not 1 <= divisor <= 12:
                raise UserError(_('La cantidad de meses para distribuir debe estar entre 1 y 12.'))
            if target:
                target.write({
                    'annual_amount': amount,
                    'distribution_month_count': divisor,
                })
            else:
                # Legacy approved lines without a header target retained the old
                # /12 logic; keep that divisor rather than changing future values.
                if protected_lines:
                    divisor = 12
                target = target_model.create({
                    'budget_id': budget.id,
                    'account_id': self.account_id.id,
                    'cost_center_id': self.cost_center_id.id or False,
                    'annual_amount': amount,
                    'distribution_month_count': divisor,
                })
                amount = target.annual_amount

        # An existing header target is the source of truth for all future months.
        amount = target.annual_amount if target else amount
        if locked_target:
            divisor = target.distribution_month_count or 12
        monthly_amount = Line._monthly_amount_from_annual(amount, budget.currency_id, divisor)
        line_vals = []
        for month in self.month_ids.sorted(key=lambda rec: rec.number):
            line_vals.append({
                'budget_id': budget.id,
                'account_id': self.account_id.id,
                'cost_center_id': self.cost_center_id.id or False,
                'month_option_id': month.id,
                'annual_amount': amount,
                'allocation_month_count': divisor,
                'planned_amount': monthly_amount,
            })
        # Use normal model.create so access rules, duplicate protection, expense
        # reconciliation, and API synchronization remain in force.
        Line.with_user(self.env.user).create(line_vals)

        return {
            'type': 'ir.actions.act_window',
            'name': budget.display_name,
            'res_model': 'expense.budget',
            'res_id': budget.id,
            'view_mode': 'form',
            'views': [(self.env.ref('expense_budget_control.view_expense_budget_form').id, 'form')],
            'target': 'current',
        }
