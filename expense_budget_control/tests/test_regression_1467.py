# -*- coding: utf-8 -*-
"""Regresiones de guardado rápido y coincidencia de fechas ERP v1.4.67."""
from unittest.mock import patch

from odoo import fields
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestGuardarPresupuestoRapido1467(TransactionCase):
    def setUp(self):
        super().setUp()
        self.sync = self.env['expense.budget.inventory.sync']
        self.company = self.env.company
        self.account = self.env['expense.budget.account'].create({
            'company_id': self.company.id, 'code': 'FAST67-A', 'name': 'Luz ERP',
        })
        self.category = self.env['expense.budget.category'].create({
            'company_id': self.company.id, 'name': 'Rubro pruebas 1467',
        })
        self.account.write({'category_id': self.category.id})
        self.center = self.env['expense.budget.cost.center'].create({
            'company_id': self.company.id, 'code': 'FAST67-C', 'name': 'Administración',
        })
        self.budget = self.env['expense.budget'].with_context(
            skip_expense_budget_consumption_on_save=True,
        ).create({'name': 'Presupuesto rápido ERP', 'year': 2026,
                  'company_id': self.company.id, 'category_id': self.category.id})
        self.line = self.env['expense.budget.line'].with_context(
            skip_expense_budget_consumption_on_save=True,
        ).create({'budget_id': self.budget.id, 'account_id': self.account.id,
                  'cost_center_id': self.center.id, 'month': '4', 'planned_amount': 100})

    def test_cambiar_solo_proyectado_no_consulta_api(self):
        with patch.object(type(self.sync), '_sync_saved_lines', side_effect=AssertionError(
                'No debería consultar consumos al editar solo Proyectado')):
            self.line.write({'planned_amount': 225})
            self.budget.write({'line_ids': [(1, self.line.id, {'planned_amount': 250})]})
        self.assertEqual(self.line.planned_amount, 250)

    def test_linea_recientemente_consultada_usa_datos_locales(self):
        self.line.write({'erp_checked_at': fields.Datetime.now()})
        with patch.object(type(self.sync), '_call', side_effect=AssertionError(
                'No descargar historial del ERP para una línea recién consultada')):
            self.sync._sync_saved_lines(self.line)

    def test_filtro_exactamente_mismo_anio_mes_centro_subcentro(self):
        # La línea única consume todos los subcentros; no crear duplicado.
        special = self.line
        rows = [
            {'Codigo': 'FAST67-A', 'Centro': 'FAST67-C   ', 'Subcentro': 'GDE   ',
             'Fecha': 'abr  7 2026 12:00:00:000', 'Valor': '45.26'},
            {'Codigo': 'FAST67-A', 'Centro': 'FAST67-C', 'Subcentro': 'VTA',
             'Fecha': 'abr  7 2026 12:00:00:000', 'Valor': '10'},
            {'Codigo': 'FAST67-A', 'Centro': 'FAST67-C', 'Subcentro': 'GDE',
             'Fecha': 'mar  7 2026 12:00:00:000', 'Valor': '999'},
            {'Codigo': 'FAST67-A', 'Centro': 'FAST67-C', 'Subcentro': 'GDE',
             'Fecha': 'abr  7 2020 12:00:00:000', 'Valor': '888'},
        ]
        self.assertEqual([r['Valor'] for r in self.sync._rows_for_saved_lines(rows, special)],
                         ['45.26', '10'])
