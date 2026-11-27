import unittest
from pathlib import Path
from test_planning_standalone import load

engine = load('engine')
upgrade = load('external_upgrade')


def row(internal, external, warehouse='A'):
    return {'TipoFactura': 'FA', 'NumeroFactura': internal, 'Factura': external,
            'CodBodega': warehouse, 'CodProducto': 'P'}


def header(ident, internal, external, count=1):
    original = row(internal, external)
    return (ident, upgrade.legacy_key(original), external, 'FA', internal, count, 'FA '+internal)


class ExternalUpgradeTests(unittest.TestCase):
    def test_simple_rekey_preserves_header_identity_and_leading_zeroes(self):
        groups, old = upgrade.header_plan([header(11, '7', '00012'), header(12, '8', '00013')])
        self.assertEqual(groups[engine.invoice_key(row('7','00012'))][0][:5],
                         (11, upgrade.legacy_key(row('7','00012')), '["FAC","00012"]', 'FAC/00012', '00012'))
        self.assertFalse(upgrade.needs_staging(groups, old))

    def test_collision_and_missing_external_are_distinct(self):
        groups, old = upgrade.header_plan([header(1,'1','001'), header(2,'2','FAC/001'),
                                          header(3,'3',''), header(4,'4','')])
        self.assertEqual([v[0] for v in groups['["FAC","001"]']], [1,2])
        self.assertEqual(len(groups),3)

    def test_original_reveals_hidden_split_before_first_group(self):
        groups, old = upgrade.header_plan([header(1,'1','001')])
        dirty, count = set(), [0]
        source = [row('1','001'), row('1','002')]
        gen = engine.iter_invoice_groups(upgrade.inspect_source(source, groups, old, dirty, count))
        self.assertEqual(next(gen)[0], '["FAC","001"]')
        self.assertEqual(dirty, {'["FAC","001"]','["FAC","002"]'})
        self.assertEqual(count,[2])
        gen.close()

    def test_ordinary_repeats_do_not_trigger_rebuild(self):
        groups, old = upgrade.header_plan([header(1,'1','001')])
        dirty, count = set(), [0]
        self.assertEqual(len(list(upgrade.inspect_source([row('1','001')]*2, groups, old, dirty, count))),2)
        self.assertFalse(dirty)
        self.assertEqual(count,[2])

    def test_legacy_fac_key_can_block_new_external_key(self):
        groups, old = upgrade.header_plan([(1,'["FAC","001"]','002','FAC','001',1,'old'),header(2,'2','001')])
        self.assertTrue(upgrade.needs_staging(groups, old))

    def test_versioned_upgrade_does_not_delete_entire_snapshot_or_commit(self):
        script = (Path(__file__).resolve().parents[1] / 'migrations/18.0.1.8.11/post-10-external-identity.py').read_text()
        self.assertNotIn('snapshot.invoice_ids.unlink()', script)
        self.assertNotIn('.commit(', script)
        self.assertIn('UPDATE dispatch_invoice i SET invoice_key=v.key', script)
        self.assertIn('SELECT DISTINCT ON (i.company_id,i.invoice_key)', script)

if __name__ == '__main__':
    unittest.main()
