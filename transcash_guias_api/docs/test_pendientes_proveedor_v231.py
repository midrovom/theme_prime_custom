"""Pruebas locales aisladas de v2.31: no sustituyen Odoo/PostgreSQL."""
import ast
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace

src = Path(__file__).resolve().parents[1] / 'models' / 'portal_accounts.py'
tree = ast.parse(src.read_text())
cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'TranscashSupplierActivatePassword')
nodes = []
for name in ('create', '_tc_reconcile_existing_supplier_accounts'):
    fn = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == name)
    fn.decorator_list = []
    nodes.append(fn)
mod = ast.fix_missing_locations(ast.Module(body=nodes, type_ignores=[]))

class AccessError(Exception):
    pass
class GenericModel:
    def create(self, vals_list):
        self.created = vals_list
        return self
    def _check_portal_user(self):
        self.checked = True

ns = {
    '_': lambda s: s, 'AccessError': AccessError,
    'models': SimpleNamespace(Model=GenericModel),
}
exec(compile(mod, str(src), 'exec'), ns)

class Registry(GenericModel):
    def __init__(self):
        self.env = SimpleNamespace(su=True, context={'tc_portal_prepare_pending': True})

reg = Registry()
ns['create'](reg, [{'usuario_id': 3, 'company_id': 1, 'activo': False}])
assert reg.checked and reg.created[0]['activo'] is False
for bad in ({'usuario_id': 3, 'company_id': 1, 'activo': True},
            {'usuario_id': 3, 'company_id': 1, 'activo': False, 'groups_id': [4]},
            {'usuario_id': 3, 'company_id': 1, 'activo': False, 'company_id2': 2}):
    try:
        ns['create'](reg, [bad])
    except AccessError:
        pass
    else:
        raise AssertionError('No debe crear acceso activo ni asignar grupos')

class User:
    def __init__(self, id, partner_id, role=None, active=True):
        self.id=id; self.partner_id=SimpleNamespace(id=partner_id); self.active=active
        self.role=role;self.share=True
    def has_group(self, xmlid):
        return xmlid == 'base.group_portal' or xmlid.endswith(self.role or '!nothing!')
class Record:
    def __init__(self, id, name, active=True):
        self.id=id; self.name=name; self.active=active
class Rows(list):
    @property
    def ids(self):return [x.id for x in self]
class Model:
    def __init__(self, rows): self.rows=rows
    def sudo(self): return self
    def with_context(self, **kwargs): return self
    def with_company(self, company): return self
    def search(self, dom, **kwargs):
        def match(x):
            for field, op, vals in dom:
                attr = getattr(x, field)
                attr = attr.id if field == 'partner_id' else attr
                if op == 'in' and attr not in vals:return False
                if op == '=' and attr != vals:return False
            return True
        return Rows([x for x in self.rows if match(x)])
    def browse(self, ids):
        ids = [ids] if isinstance(ids, int) else ids
        found = Rows([x for x in self.rows if x.id in ids])
        return found[0] if len(found)==1 and len(ids)==1 else found
class Guides(Model):
    def read_group(self, *args, **kwargs):
        return [{'transport_partner_id': (partner, 'Proveedor'), 'company_id': (company, 'Transcash')}
                for partner,company in ((1, 1),(1,2),(2,1),(3,1),(4,1),(5,1),(6,1),(7,1))]
class Env(dict):
    def __init__(self):
        super().__init__()
        self.su=True
        self.user=SimpleNamespace(share=False)
        self.cr=SimpleNamespace(savepoint=lambda: nullcontext())
        self['tc.guide']=Guides([])
        self['res.company']=Model([Record(1,'A'),Record(2,'B')])
        self['res.partner']=Model([
            Record(1,'TRANSPORTES UNO'),
            Record(2,'TRANSPORTE PROPORCIONADO POR CLIENTE'),
            Record(3,'CONDUCTOR X'),Record(4,'CLIENTE Y'),
            Record(5,'DUPLICADO'),Record(6,'INACTIVO'),Record(7,'TRANSPORTES YA REVISADOS'),
        ])
        self['res.users']=Model([
            User(10,1),User(20,2),User(30,3,'group_transcash_chofer'),
            User(40,4,'group_transcash_cliente'),User(50,5),User(51,5),
            User(60,6,active=False),User(70,7),
        ])
class Supplier:
    def __init__(self):
        self.env=Env();self.existing={(70,1)};self.new=[]
    def sudo(self):return self
    def with_company(self, company):return self
    def search(self, dom, limit=1):
        key=(dom[0][2],dom[1][2])
        return [True] if key in self.existing else []
    def _tc_register_pending_access(self,user,company,role):
        assert role=='supplier'
        self.new.append((user.id,company.id))
        self.existing.add((user.id,company.id))
        return True,''
    # El código de producción invoca esta operación a través de self.env['tc.guide'];
    # el fake usa el propio método enlazado para recoger resultados.

test=Supplier()
test.env['tc.guide']._tc_register_pending_access=test._tc_register_pending_access
ns['_logger']=SimpleNamespace(warning=lambda *a,**kw:None)
res=ns['_tc_reconcile_existing_supplier_accounts'](test)
assert res == {'reviewed':3,'created':2,'skipped':5},res
assert set(test.new)=={(10,1),(10,2),(70,1)},test.new
print('OK: acceso inactivo técnico, solo lista blanca, recuperación, múltiples compañías y exclusiones')
