import unittest
from importlib.util import spec_from_file_location, module_from_spec
from pathlib import Path
from test_planning_standalone import load

engine = load('engine')
ROOT = Path(__file__).resolve().parents[1]


def migration(name):
    spec = spec_from_file_location('migration_' + name[:3], ROOT / 'migrations/18.0.1.8.14' / name)
    mod = module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class Cursor:
    def __init__(self, incompatible=False):
        self.calls = []
        self.incompatible = incompatible
        self.rowcount = 12
    def execute(self, sql):
        self.calls.append(sql)
    def fetchone(self):
        return (self.incompatible,)


class SafeExternalLabelTests(unittest.TestCase):
    def test_same_external_different_internal_stays_distinct(self):
        a = {'TipoFactura':'FA','NumeroFactura':'320484','Factura':'16039'}
        b = dict(a, NumeroFactura='321111')
        self.assertEqual(engine.invoice_display_name(a), 'FAC/16039')
        self.assertEqual(engine.invoice_display_name(a), engine.invoice_display_name(b))
        self.assertNotEqual(engine.invoice_key(a), engine.invoice_key(b))
        self.assertEqual(len(list(engine.iter_invoice_groups([a,b]))),2)
    def test_label_formats(self):
        row = {'TipoFactura':'FA','NumeroFactura':'20'}
        self.assertEqual(engine.invoice_display_name(dict(row,Factura=' 0007 ')), 'FAC/0007')
        self.assertEqual(engine.invoice_display_name(dict(row,Factura='fac/ 0007 ')), 'FAC/0007')
        self.assertEqual(engine.invoice_display_name(row), 'FAC/SIN NÚMERO EXTERNO (FA 20)')
    def test_modern_upgrade_executes_no_queries(self):
        for ver in ['18.0.1.8.10', '18.0.1.8.13', '1.8.10']:
            cr = Cursor(True)
            migration('pre-10-check-version.py').migrate(cr, ver)
            self.assertEqual(cr.calls, [])
    def test_completed_bad_upgrade_aborts_without_writes(self):
        for ver in ['18.0.1.8.11','18.0.1.8.12','1.8.12']:
            cr=Cursor()
            with self.assertRaises(ValueError):
                migration('pre-10-check-version.py').migrate(cr,ver)
            self.assertEqual(cr.calls,[])
    def test_no_previous_external_migrations_or_post_script(self):
        for ver in ('11', '12', '13'):
            self.assertFalse((ROOT / ('migrations/18.0.1.8.' + ver)).exists())
        self.assertFalse(list((ROOT / 'migrations/18.0.1.8.14').glob('post-*.py')))
    def test_dynamic_display_does_not_write_legacy_name(self):
        from types import SimpleNamespace
        from test_import_queue_standalone import load_model
        cls = load_model('invoice').DispatchInvoice
        rows = [SimpleNamespace(name='FA 320484', external_number='0007', invoice_type='FA', internal_number='320484'),
                SimpleNamespace(name='FA 320485', external_number='fac/ 0007 ', invoice_type='FA', internal_number='320485')]
        cls._compute_display_name(rows)
        self.assertEqual([r.display_name for r in rows], ['FAC/0007', 'FAC/0007'])
        self.assertEqual([r.name for r in rows], ['FA 320484', 'FA 320485'])
        self.assertEqual(cls._search_display_name(None, 'ilike', 'FAC/0007'),
                         ['|', ('external_number', 'ilike', '0007'), ('external_number', 'ilike', 'FAC/0007')])
    def test_views_use_dynamic_name(self):
        import xml.etree.ElementTree as ET
        root = ET.parse(ROOT / 'views/invoice_views.xml').getroot()
        for ident in ('invoice_search', 'invoice_list', 'invoice_form'):
            rec = root.find("record[@id='%s']" % ident)
            arch = rec.find("field[@name='arch']")
            self.assertIsNotNone(arch.find('.//field[@name="display_name"]'))
            self.assertIsNone(arch.find('.//field[@name="name"]'))

if __name__ == '__main__': unittest.main()
