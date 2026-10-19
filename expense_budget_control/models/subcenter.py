# -*- coding: utf-8 -*-
"""Subcentros observados en getconsumosgastos/2, vinculados a un centro ERP."""
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ExpenseBudgetSubcenter(models.Model):
    _name = 'expense.budget.subcenter'
    _description = 'Subcentro de costo recibido del ERP'
    _order = 'center_id, code'
    _rec_name = 'code'
    _check_company_auto = True

    code = fields.Char(string='Subcentro', required=True, index=True)
    company_id = fields.Many2one('res.company', string='Empresa', required=True,
                                 default=lambda self: self.env.company, index=True)
    center_id = fields.Many2one('expense.budget.cost.center', string='Centro de costo',
                                required=True, index=True, ondelete='cascade', check_company=True)

    _sql_constraints = [
        ('company_center_code_uniq',
         'unique(company_id, center_id, code)',
         'El subcentro ya existe para ese centro de costo y empresa.'),
    ]

    @api.constrains('center_id', 'company_id')
    def _check_center_company(self):
        for rec in self:
            if rec.center_id.company_id != rec.company_id:
                raise ValidationError(_('El subcentro debe pertenecer a la empresa de su centro de costo.'))

    def name_get(self):
        return [(rec.id, rec.code) for rec in self]
