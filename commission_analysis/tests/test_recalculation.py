from datetime import date

from odoo.tests.common import TransactionCase


class TestCommissionRecalculation(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.operator = cls.env['commission.operator'].create({
            'name': 'Operador Test',
            'code': 'OPTEST',
            'icc_match_length': 18,
        })
        cls.sim = cls.env['commission.sim'].create({
            'operator_id': cls.operator.id,
            'icc': '895930100100000001',
            'icc_key': '895930100100000001',
            'purchase_date': date(2025, 1, 1),
            'purchase_cost': 1.0,
        })

    def _batch(self, name='TEST'):
        return self.env['commission.settlement.batch'].create({
            'name': name,
            'operator_id': self.operator.id,
            'period': 'TEST',
        })

    def test_recalculate_without_rules_accepts_null_many2one(self):
        """Regression: all NULL scheme_line_id values must not be inferred as SQL text."""
        batch = self._batch('NO-RULE')
        line = self.env['commission.settlement.line'].create({
            'batch_id': batch.id,
            'sim_id': self.sim.id,
            'icc': self.sim.icc,
            'icc_key': self.sim.icc_key,
            'compensation_date': date(2025, 2, 1),
            'product': 'CLARO CHIP',
            'concept': 'SIN REGLA',
            'reported_value': 0.50,
            'source_file': 'test.xlsx [abc]',
            'source_row': 3,
        })
        # Exercise the typed execute_values path directly, then the batch fast path.
        line._recalculate_expected_bulk()
        batch.action_recalculate()
        line.invalidate_recordset()
        self.assertFalse(line.scheme_line_id)
        self.assertEqual(line.reconciliation_state, 'no_rule')
        self.assertEqual(line.expected_value, 0.0)

    def test_recalculate_links_sim_loaded_after_settlement(self):
        batch = self._batch('LINK-LATER')
        key = '895930100100000002'
        line = self.env['commission.settlement.line'].create({
            'batch_id': batch.id,
            'icc': key + '7',
            'icc_key': key,
            'compensation_date': date(2025, 2, 1),
            'product': 'CLARO CHIP',
            'concept': 'SIN REGLA',
            'reported_value': 0.30,
            'reconciliation_state': 'no_purchase',
            'source_file': 'before_purchase.xlsx [def]',
            'source_row': 3,
        })
        sim = self.env['commission.sim'].create({
            'operator_id': self.operator.id,
            'icc': key,
            'icc_key': key,
            'purchase_date': date(2025, 1, 1),
            'purchase_cost': 1.0,
        })
        batch.action_recalculate()
        line.invalidate_recordset()
        self.assertEqual(line.sim_id, sim)
        self.assertEqual(line.reconciliation_state, 'no_rule')


    def test_bulk_recalculation_accepts_mixed_rule_and_null_many2one(self):
        """Mixed VALUES rows must keep scheme_line_id typed as integer even with NULLs."""
        scheme = self.env['commission.scheme'].create({
            'name': 'Mixto',
            'operator_id': self.operator.id,
            'product': 'Prepago',
            'product_match_pattern': 'CLARO CHIP',
            'date_from': date(2025, 1, 1),
            'date_to': date(2025, 12, 31),
        })
        self.env['commission.scheme.line'].create({
            'scheme_id': scheme.id,
            'concept_code': 'BASE',
            'concept_name': 'Base',
            'match_pattern': 'BASE',
            'base_field': 'consumption',
            'min_amount': 0,
            'no_upper_limit': True,
            'percentage': 20,
        })
        scheme.action_activate()

        batch = self._batch('MIXED')
        matching = self.env['commission.settlement.line'].create({
            'batch_id': batch.id, 'sim_id': self.sim.id,
            'icc': self.sim.icc, 'icc_key': self.sim.icc_key,
            'compensation_date': date(2025, 3, 1), 'product': 'CLARO CHIP',
            'concept': 'BASE', 'evaluated_consumption': 10.0, 'reported_value': 2.0,
            'source_file': 'mixed.xlsx [1]', 'source_row': 3,
        })
        no_rule = self.env['commission.settlement.line'].create({
            'batch_id': batch.id, 'sim_id': self.sim.id,
            'icc': self.sim.icc, 'icc_key': self.sim.icc_key,
            'compensation_date': date(2025, 3, 1), 'product': 'CLARO CHIP',
            'concept': 'OTRO', 'evaluated_consumption': 10.0, 'reported_value': 1.0,
            'source_file': 'mixed.xlsx [1]', 'source_row': 4,
        })
        (matching | no_rule)._recalculate_expected_bulk()
        matching.invalidate_recordset()
        no_rule.invalidate_recordset()
        self.assertTrue(matching.scheme_line_id)
        self.assertEqual(matching.reconciliation_state, 'ok')
        self.assertFalse(no_rule.scheme_line_id)
        self.assertEqual(no_rule.reconciliation_state, 'no_rule')

    def test_missing_compensation_date_is_data_error(self):
        batch = self._batch('MISSING-DATE')
        line = self.env['commission.settlement.line'].create({
            'batch_id': batch.id, 'sim_id': self.sim.id,
            'icc': self.sim.icc, 'icc_key': self.sim.icc_key,
            'product': 'CLARO CHIP', 'concept': 'SIN FECHA', 'reported_value': 1.0,
            'source_file': 'missing-date.xlsx [2]', 'source_row': 3,
        })
        line._recalculate_expected_bulk()
        line.invalidate_recordset()
        self.assertEqual(line.reconciliation_state, 'data_error')
        self.assertFalse(line.scheme_line_id)

    def test_closed_scheme_remains_valid_for_historical_recalculation(self):
        scheme = self.env['commission.scheme'].create({
            'name': 'Histórico',
            'operator_id': self.operator.id,
            'product': 'Prepago',
            'product_match_pattern': 'CLARO CHIP',
            'date_from': date(2025, 1, 1),
            'date_to': date(2025, 12, 31),
        })
        self.env['commission.scheme.line'].create({
            'scheme_id': scheme.id,
            'concept_code': 'BASE',
            'concept_name': 'Base 20',
            'match_pattern': 'BASE 20',
            'base_field': 'consumption',
            'min_amount': 0,
            'max_amount': 0,
            'no_upper_limit': True,
            'percentage': 20,
        })
        scheme.action_activate()
        scheme.action_close()

        batch = self._batch('HIST')
        line = self.env['commission.settlement.line'].create({
            'batch_id': batch.id,
            'sim_id': self.sim.id,
            'icc': self.sim.icc,
            'icc_key': self.sim.icc_key,
            'compensation_date': date(2025, 6, 1),
            'product': 'CLARO CHIP',
            'concept': 'BASE 20',
            'evaluated_consumption': 10.0,
            'reported_value': 2.0,
            'source_file': 'historical.xlsx [ghi]',
            'source_row': 3,
        })
        batch.action_recalculate()
        line.invalidate_recordset()
        self.assertEqual(line.reconciliation_state, 'ok')
        self.assertAlmostEqual(line.expected_value, 2.0, places=2)
