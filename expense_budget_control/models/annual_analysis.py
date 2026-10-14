# -*- coding: utf-8 -*-
"""Comparativo anual por presupuesto y cuenta, a partir de proyecciones mensuales.

Cada fila agrupa los doce meses de una misma cuenta en un mismo presupuesto/año.
Los subtotales por rubro y cuenta pueden agrupar varios presupuestos del mismo año.
El alcance duplicado por estados permite ocultar los borradores al Aprobador
sin alterar lo que ve el Administrador. Las reglas permiten leer un solo alcance.
"""

from odoo import fields, models, tools


class ExpenseBudgetAnnualAnalysis(models.Model):
    _name = 'expense.budget.annual.analysis'
    _description = 'Proyectado vs. real anual por presupuesto y cuenta'
    _auto = False
    _rec_name = 'account_id'
    _order = 'year desc, category_id, account_id, budget_id'

    budget_id = fields.Many2one('expense.budget', string='Presupuesto', readonly=True)
    year = fields.Integer(string='Año', readonly=True)
    company_id = fields.Many2one('res.company', string='Empresa', readonly=True)
    currency_id = fields.Many2one('res.currency', string='Moneda', readonly=True)
    category_id = fields.Many2one('expense.budget.category', string='Rubro', readonly=True)
    account_id = fields.Many2one('expense.budget.account', string='Cuenta controlada', readonly=True)
    planned_amount = fields.Monetary(string='Proyectado', currency_field='currency_id', readonly=True)
    actual_amount = fields.Monetary(string='Consumido', currency_field='currency_id', readonly=True)
    variance_amount = fields.Monetary(string='Disponible', currency_field='currency_id', readonly=True)
    # El porcentaje debe calcularse a partir de las sumas, nunca sumar porcentajes.
    execution_percentage = fields.Float(string='Ejecución (%)', digits=(16, 2),
                                        aggregator=False, readonly=True)
    line_count = fields.Integer(string='Meses incluidos', readonly=True, aggregator='sum')
    scope = fields.Selection([
        ('all', 'Todos los estados'),
        ('non_draft', 'Pendientes de aprobación y aprobados'),
    ], string='Alcance interno', readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE VIEW %s AS (
                WITH scoped_lines AS (
                    SELECT l.id AS line_id, b.id AS budget_id,
                           b.company_id, b.year, l.account_id,
                           a.category_id, l.planned_amount, l.actual_amount,
                           'all'::varchar AS scope
                      FROM expense_budget_line l
                      JOIN expense_budget b ON b.id = l.budget_id
                      JOIN expense_budget_account a ON a.id = l.account_id
                    UNION ALL
                    SELECT l.id AS line_id, b.id AS budget_id,
                           b.company_id, b.year, l.account_id,
                           a.category_id, l.planned_amount, l.actual_amount,
                           'non_draft'::varchar AS scope
                      FROM expense_budget_line l
                      JOIN expense_budget b ON b.id = l.budget_id
                      JOIN expense_budget_account a ON a.id = l.account_id
                     WHERE b.state IN ('to_approve', 'approved')
                )
                SELECT (MIN(s.line_id)::bigint * 2 +
                        CASE WHEN s.scope = 'non_draft' THEN 1 ELSE 0 END) AS id,
                       s.budget_id, s.company_id, s.year,
                       s.account_id, s.category_id, c.currency_id, s.scope,
                       COUNT(*)::integer AS line_count,
                       SUM(s.planned_amount) AS planned_amount,
                       SUM(s.actual_amount) AS actual_amount,
                       SUM(s.planned_amount) - SUM(s.actual_amount) AS variance_amount,
                       CASE WHEN SUM(s.planned_amount) != 0
                            THEN SUM(s.actual_amount) * 100.0 / SUM(s.planned_amount)
                            ELSE 0.0 END AS execution_percentage
                  FROM scoped_lines s
                  JOIN res_company c ON c.id = s.company_id
                 GROUP BY s.budget_id, s.company_id, s.year,
                          s.account_id, s.category_id, c.currency_id, s.scope
            )
        """ % self._table)
