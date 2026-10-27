"""Pruebas aisladas de la resolución de transportista por documento.
No necesitan el servidor Odoo: se ejercita el método real extraído del fuente.
"""
import ast
import logging
from pathlib import Path
from types import SimpleNamespace
import unittest

MODULE = Path(__file__).resolve().parents[1] / 'models' / 'partner_link.py'
source = MODULE.read_text()
parsed = ast.parse(source)
clazz = next(n for n in parsed.body if isinstance(n, ast.ClassDef) and n.name == 'TCGuidePartnerLink')
method = next(n for n in clazz.body if isinstance(n, ast.FunctionDef) and n.name == '_resolve_transport_partner')
klass = ast.ClassDef(name='UnderTest', bases=[], keywords=[], body=[method], decorator_list=[])
namespace = {
    '__name__': __name__,
    '_': lambda v: v,
    '_clean': lambda v: '' if not v else str(v).strip(),
    '_logger': logging.getLogger(__name__),
    'fiscal_document': lambda v: ''.join(ch for ch in str(v or '').upper() if ch.isalnum()),
    'fiscal_key': lambda v: ''.join(ch for ch in str(v or '').upper() if ch.isalnum()),
}
created = []

class Partner:
    def __init__(self, doc, name, pid, active=True):
        self.vat, self.name, self.id, self.active = doc, name, pid, active
        self.is_company = True
        self.company_id = False
        self.supplier_rank = 0
    def write(self, vals):
        for key, value in vals.items(): setattr(self, key, value)
    def sudo(self): return self

class Records(list):
    def filtered(self, criterion):
        if isinstance(criterion, str):
            return Records([r for r in self if getattr(r, criterion)])
        return Records([r for r in self if criterion(r)])
    def sudo(self): return self
    def __getattr__(self, attr):
        if len(self)==1: return getattr(self[0], attr)
        raise AttributeError(attr)

class Partners:
    _fields = {'supplier_rank', 'l10n_latam_identification_type_id'}
    def __init__(self, records): self.records = records
    def sudo(self): return self
    def with_context(self, **kwargs): return self
    def browse(self): return Records()
    def search(self, domain):
        name = next((v for k, op, v in domain if k=='name'), '')
        return Records([p for p in self.records if p.name.upper()==name.upper()])

class Cursor:
    def execute(self, query, params): pass

class Env:
    def __init__(self, partner_model):
        self.partner_model = partner_model
        self.cr = Cursor()
    def __getitem__(self, model):
        return self.partner_model

class GuideBase:
    def __init__(self, records):
        self.company_id = SimpleNamespace(id=1)
        self.partners = Partners(records)
        self.env = Env(self.partners)
    def ensure_one(self): return None
    def _partner_by_tax(self, doc):
        matched = [p for p in self.partners.records if ''.join(x for x in p.vat if x.isalnum())==doc]
        return (matched[0], '') if matched else (False, '')


def fake_create(env, vals, doc, role):
    partner = Partner(doc, vals['name'], len(env['res.partner'].records)+1)
    env['res.partner'].records.append(partner)
    created.append((doc, role))
    return partner, 'foreign', ''
namespace['create_fiscal_partner'] = fake_create
exec(compile(ast.fix_missing_locations(ast.Module(body=[klass], type_ignores=[])), str(MODULE), 'exec'), namespace)
UnderTest = namespace['UnderTest']

class ActualGuide(UnderTest, GuideBase): pass

class ForeignTransportTests(unittest.TestCase):
    def setUp(self): created.clear()
    def test_generic_name_same_different_id_can_create(self):
        records = [Partner('765432109', 'TRANSPORTE PROPORCIONADO POR CLIENTE', 1)]
        guide = ActualGuide(records)
        partner, _ = guide._resolve_transport_partner('TRANSPORTE PROPORCIONADO POR CLIENTE', '123456789')
        self.assertEqual(partner.vat,'123456789')
        self.assertEqual(len(records),2)
        self.assertEqual(created, [('123456789', 'transport')])
        again, _ = guide._resolve_transport_partner('TRANSPORTE PROPORCIONADO POR CLIENTE', '123456789')
        self.assertEqual(again.id, partner.id)
        self.assertEqual(len(records),2)
        self.assertEqual(len(created),1)
    def test_normal_name_different_doc_is_not_merged(self):
        records = [Partner('1234567890123', 'Transportes Costa', 1)]
        guide = ActualGuide(records)
        p,_ = guide._resolve_transport_partner('Transportes Costa','987654321')
        self.assertEqual(p.vat, '987654321')
        self.assertEqual(len(records),2)
    def test_no_identifier_does_not_create_generic(self):
        guide = ActualGuide([])
        p, note = guide._resolve_transport_partner('TRANSPORTE PROPORCIONADO POR CLIENTE','')
        self.assertFalse(p)
        self.assertIn('sin identificación', note)
        self.assertEqual(created,[])

if __name__=='__main__': unittest.main(verbosity=2)
