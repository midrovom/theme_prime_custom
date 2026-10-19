# -*- coding: utf-8 -*-
"""Catálogo independiente de centros de costo (por empresa)."""
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ExpenseBudgetCostCenter(models.Model):
    _name = 'expense.budget.cost.center'
    _description = 'Centro de costo presupuestario'
    _order = 'code, name'
    _check_company_auto = True

    code = fields.Char(string='Código', required=True, index=True)
    name = fields.Char(string='Centro de costo', required=True)
    company_id = fields.Many2one('res.company', string='Empresa', required=True,
                                 default=lambda self: self.env.company, index=True)
    active = fields.Boolean(default=True)
    description = fields.Text(string='Observaciones')
    budget_line_ids = fields.One2many('expense.budget.line', 'cost_center_id',
                                      string='Proyecciones mensuales')
    _sql_constraints = [
        ('expense_cost_center_company_code_uniq', 'unique(company_id, code)',
         'El código del centro de costo ya existe para esta empresa.'),
    ]

    @api.constrains('code')
    def _check_code(self):
        for rec in self:
            if not (rec.code or '').strip():
                raise ValidationError(_('El código del centro de costo es obligatorio.'))

    def name_get(self):
        return [(rec.id, '%s - %s' % (rec.code, rec.name)) for rec in self]
