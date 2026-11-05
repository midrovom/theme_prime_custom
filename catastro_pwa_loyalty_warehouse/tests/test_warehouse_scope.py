"""Run without Odoo: python -m unittest discover -s tests -p 'test_*.py'."""
import unittest
from warehouse_rules import warehouse_scope_domain


def matches_scope(scope, warehouse_ids):
    """Evaluate only the simple domain shapes produced by our scope helper."""
    if len(scope) == 1:
        return not warehouse_ids
    assert scope[0] == '|'
    assert scope[1][1:] == ('=', False)
    assert scope[2][1] == 'in'
    return not warehouse_ids or any(w in warehouse_ids for w in scope[2][2])


class WarehouseScopeTests(unittest.TestCase):
    def test_two_allowed_warehouses_one_denied(self):
        program_warehouses = {101, 102}
        self.assertTrue(matches_scope(warehouse_scope_domain(101), program_warehouses))
        self.assertTrue(matches_scope(warehouse_scope_domain(102), program_warehouses))
        self.assertFalse(matches_scope(warehouse_scope_domain(103), program_warehouses))

    def test_existing_promotions_without_warehouse_restrictions(self):
        for warehouse in (101, 102, 103, None):
            self.assertTrue(matches_scope(warehouse_scope_domain(warehouse), set()))

    def test_no_warehouse_cannot_claim_a_restricted_promotion(self):
        self.assertFalse(matches_scope(warehouse_scope_domain(None), {101}))

    def test_promo_codes_are_scoped_by_related_program(self):
        scope = warehouse_scope_domain(101, 'program_id.')
        self.assertEqual(scope, [
            '|', ('program_id.catastro_warehouse_ids', '=', False),
            ('program_id.catastro_warehouse_ids', 'in', [101]),
        ])

    def test_warehouse_ids_preserve_int_ids(self):
        self.assertEqual(warehouse_scope_domain('001'), [
            '|', ('catastro_warehouse_ids', '=', False),
            ('catastro_warehouse_ids', 'in', [1]),
        ])


if __name__ == '__main__':
    unittest.main()
