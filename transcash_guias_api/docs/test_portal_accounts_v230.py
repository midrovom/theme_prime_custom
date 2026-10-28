"""Pruebas aisladas de lógica Portal (sin arrancar Odoo).

Ejecutar: python docs/test_portal_accounts_v230.py
Son pruebas con dobles; NO sustituyen las pruebas de integración en PostgreSQL.
"""
import ast
import logging
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace

BASE = Path(__file__).resolve().parents[1]
tree = ast.parse((BASE / 'models' / 'portal_accounts.py').read_text())
cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'TcGuidePortalAccounts')
functions = []
for name in ('_tc_existing_or_new_user', '_tc_register_pending_access'):
    node = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == name)
    node.decorator_list = []
    functions.append(node)
module = ast.fix_missing_locations(ast.Module(body=functions, type_ignores=[]))

class TestError(Exception):
    pass

def document(value):
    import re
    return re.sub(r'[^A-Z0-9]', '', str(value or '').upper())

ns = {'_': lambda x: x, 'fiscal_document': document, 'SUPERUSER_ID': 1,
      '_logger': logging.getLogger(__name__), 'ValidationError': TestError,
      'UserError': TestError, 'AccessError': TestError}
exec(compile(module, '<portal-helper>', 'exec'), ns)

class RecordSet(list):
    @property
    def id(self):
        return self[0].id if self else False
    def __getattr__(self, name):
        if self and len(self) == 1:
            return getattr(self[0], name)
        raise AttributeError(name)

class PortalUser:
    def __init__(self, **kw):
        self.__dict__.update(kw)
        self.share = True
        self.active = kw.get('active', True)
    def has_group(self, name):
        return name == 'base.group_portal'

class InMemoryModel:
    def __init__(self, records=None):
        self.rows = records or []
        self._id = len(self.rows) + 1
    def with_user(self, *args): return self
    def with_company(self, *args): return self
    def with_context(self, **kwargs): return self
    def search(self, domain, limit=None):
        filt = [r for r in self.rows if all(
            getattr(r, key, None) == value for key, operator, value in domain
            if operator == '=')]
        return RecordSet(filt[:limit] if limit else filt)
    def browse(self, ids):
        return RecordSet([r for r in self.rows if r.id in ids])
    def create(self, values):
        v = dict(values)
        v.pop('groups_id', None)
        rec = PortalUser(**v)
        rec.id = self._id
        self._id += 1
        self.rows.append(rec)
        return rec

class Cursor:
    def savepoint(self): return nullcontext()
    def execute(self, statement, values): self.values = values
    def fetchall(self): return []

class Environment(dict):
    def __init__(self):
        super().__init__()
        self['res.users'] = InMemoryModel()
        self['tc.portal.password.state'] = InMemoryModel()
        self['transcash.acceso.proveedor'] = InMemoryModel()
        self['transcash.acceso.cliente'] = InMemoryModel()
        self.cr = Cursor()
    def ref(self, name): return SimpleNamespace(id=2)

class Caller:
    def __init__(self, env): self.env=env
    _tc_existing_or_new_user = ns['_tc_existing_or_new_user']
    _tc_register_pending_access = ns['_tc_register_pending_access']


def main():
    env = Environment()
    caller = Caller(env)
    company = SimpleNamespace(id=1)
    partner = SimpleNamespace(id=82, vat='1790013235001', name='Transportista 1',
                              display_name='Transportista 1', active=True)
    user, msg = caller._tc_existing_or_new_user(partner, company, 'supplier')
    assert user.login == '1790013235001' and user.password == '1790013235001'
    assert user.active and user.share
    assert len(env['tc.portal.password.state'].rows) == 1
    entry, _ = caller._tc_register_pending_access(user, company, 'supplier')
    assert entry.activo is False and entry.usuario_id == user.id
    same, _ = caller._tc_existing_or_new_user(partner, company, 'supplier')
    assert same.id == user.id and len(env['res.users'].rows) == 1
    same_entry, _ = caller._tc_register_pending_access(same, company, 'supplier')
    assert same_entry.id == entry.id and len(env['transcash.acceso.proveedor'].rows) == 1
    different = SimpleNamespace(id=83, vat='1790013235001', name='Transportista otro',
                                display_name='Transportista otro', active=True)
    no_user, conflict = caller._tc_existing_or_new_user(different, company, 'supplier')
    assert not no_user and 'otro contacto' in conflict
    no_id = SimpleNamespace(id=84, vat=False, name='Destinatario NAJ',
                            display_name='Destinatario NAJ', active=True)
    no_user, warn = caller._tc_existing_or_new_user(no_id, company, 'recipient')
    assert not no_user and 'identificación suficiente' in warn
    print('OK: alta, contraseña inicial, pendientes, idempotencia, colisión e identificación ausente')

if __name__ == '__main__': main()
