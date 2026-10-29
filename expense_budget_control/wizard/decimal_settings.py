# -*- coding: utf-8 -*-
"""Administrar la precisión de los importes presupuestarios sin cambiar monedas."""
from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError


class ExpenseBudgetDecimalSettings(models.TransientModel):
    _name = 'expense.budget.decimal.settings'
    _description = 'Precisión decimal de importes presupuestarios'

    digits = fields.Selection(
        [(str(n), '%s decimales' % n) for n in range(2, 9)],
        string='Decimales a mostrar y calcular', required=True, default='2',
        help='Se aplica únicamente a los importes de los presupuestos de gastos. No cambia la moneda de Odoo ni los movimientos contables.',
    )

    @api.model
    def default_get(self, field_list):
        result = super().default_get(field_list)
        if 'digits' in field_list:
            configured = self.env['decimal.precision'].precision_get('Presupuesto de Gastos')
            result['digits'] = str(configured) if 2 <= configured <= 8 else '2'
        return result

    def action_save(self):
        self.ensure_one()
        if not self.env.user.has_group('expense_budget_control.group_expense_budget_manager'):
            raise AccessError(_('Solo el administrador de presupuestos puede cambiar la precisión decimal.'))
        digits = int(self.digits)
        if not 2 <= digits <= 8:
            raise ValidationError(_('Seleccione entre 2 y 8 decimales.'))
        precision = self.env.ref('expense_budget_control.expense_budget_amount_precision', raise_if_not_found=False)
        if not precision:
            precision = self.env['decimal.precision'].sudo().search([('name', '=', 'Presupuesto de Gastos')], limit=1)
        if not precision:
            precision = self.env['decimal.precision'].sudo().create({'name': 'Presupuesto de Gastos', 'digits': digits})
        else:
            precision.sudo().write({'digits': digits})
        return {
            'type': 'ir.actions.client', 'tag': 'display_notification',
            'params': {
                'title': _('Precisión decimal actualizada'),
                'message': _('Se usarán %s decimales. Recargue la vista para visualizar la nueva precisión.') % digits,
                'type': 'success', 'sticky': False,
                'next': {'type': 'ir.actions.act_window_close'},
            },
        }
