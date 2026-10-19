# -*- coding: utf-8 -*-
"""Tres endpoints ERP: catálogo de cuentas, centros y consumos.

No almacena credenciales nuevas: usa exclusivamente api.administrator. No elimina
movimientos ausentes de respuestas sucesivas, que podrían ser consultas parciales.
"""
from collections import defaultdict
from datetime import datetime
from decimal import Decimal
import hashlib
import logging

from odoo import api, models, _
from odoo.exceptions import UserError

from .expense import as_text, get_value, parse_amount

_logger = logging.getLogger(__name__)

ENDPOINTS = {
    'accounts': 'inventory_odoo/consulta_odoo/getctagastos/2',
    'centers': 'inventory_odoo/consulta_odoo/getcentrocostos/2',
    'consumptions': 'inventory_odoo/consulta_odoo/getconsumosgastos/2',
}

SPANISH_MONTHS = {
    'ene': 1, 'feb': 2, 'mar': 3, 'abr': 4, 'may': 5, 'jun': 6,
    'jul': 7, 'ago': 8, 'sep': 9, 'sept': 9, 'oct': 10, 'nov': 11, 'dic': 12,
    'jan': 1, 'apr': 4, 'aug': 8, 'dec': 12,
}


def parse_erp_date(value):
    """Ejemplo: abr 25 2026 12:00:00:000; sin depender del locale del SO."""
    value = as_text(value)
    for fmt in ('%Y-%m-%d', '%Y-%m-%d %H:%M:%S', '%d/%m/%Y', '%d-%m-%Y'):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            pass
    parts = value.split()
    if len(parts) >= 3:
        month = SPANISH_MONTHS.get(parts[0].lower().strip('.'))
        if month:
            try:
                return datetime(int(parts[2]), month, int(parts[1])).date()
            except ValueError:
                pass
    raise ValueError(_('Fecha de consumo no reconocida: %s') % value)


class ExpenseBudgetInventorySync(models.AbstractModel):
    _name = 'expense.budget.inventory.sync'
    _description = 'Importación ERP de cuentas, centros de costo y consumos'

    @api.model
    def _rows(self, response):
        if isinstance(response, dict):
            if response.get('success') is False:
                raise ValueError(as_text(response.get('message')) or 'La API reportó error.')
            payload = response.get('data', response.get('items', response.get('result')))
        else:
            payload = response
        if isinstance(payload, dict):
            for key in ('data', 'items', 'result', 'cuentas', 'centros'):
                if isinstance(payload.get(key), list):
                    payload = payload[key]
                    break
        if not isinstance(payload, list):
            raise ValueError('La API debe devolver un arreglo data de registros JSON.')
        if len(payload) > 100000:
            raise ValueError('Límite de 100.000 registros por consulta.')
        if any(not isinstance(row, dict) for row in payload):
            raise ValueError('Todos los registros de la API deben ser objetos JSON.')
        return payload

    @api.model
    def _validate_api(self, company, record, kind):
        if not record:
            return False
        if record.company_id != company or record.type != 'get' or record.status != 'A':
            raise UserError(_('La API de %s debe ser GET, estar activa y pertenecer a la empresa.') % kind)
        # Se usa la URL/endpoint ya configurados en API Administrator.
        # No modificar credenciales ni fabricar conexiones alternativas.
        expected = ENDPOINTS[kind].rstrip('/').lower()
        current = as_text(record.end_point).strip('/').lower()
        if not current.endswith(expected):
            raise UserError(_('La API de %(kind)s debe tener el endpoint %(path)s en API Administrator.') % {
                'kind': kind, 'path': ENDPOINTS[kind],
            })
        return True

    @api.model
    def _call(self, company, record, kind):
        self._validate_api(company, record, kind)
        response = self.env['api.administrator'].sudo().call_api(
            record.name, method='get', company_id=company.id,
        )
        return self._rows(response)

    @api.model
    def _sync_accounts(self, company, rows):
        Account = self.env['expense.budget.account'].sudo().with_company(company)
        clean = {}
        for index, item in enumerate(rows, 1):
            code = as_text(get_value(item, 'Codigo', 'code', required=True))
            name = as_text(get_value(item, 'Nombre', 'name', required=True))
            if not code or not name:
                raise ValueError('La cuenta %s necesita Codigo y Nombre.' % index)
            if code in clean and clean[code] != name:
                raise ValueError('Código de cuenta duplicado con nombres diferentes: %s' % code)
            clean[code] = name
        existing = {rec.code: rec for rec in Account.search([
            ('company_id', '=', company.id), ('code', 'in', list(clean)),
        ])}
        counts = {'created': 0, 'updated': 0, 'unchanged': 0}
        for code, name in clean.items():
            rec = existing.get(code)
            if not rec:
                Account.create({'company_id': company.id, 'code': code, 'name': name})
                counts['created'] += 1
            elif rec.name != name:
                rec.write({'name': name})
                counts['updated'] += 1
            else:
                counts['unchanged'] += 1
        return counts

    @api.model
    def _sync_centers(self, company, rows):
        Center = self.env['expense.budget.cost.center'].sudo().with_company(company)
        clean = {}
        for index, item in enumerate(rows, 1):
            code = as_text(get_value(item, 'Codigo', 'code', required=True))
            name = as_text(get_value(item, 'Nombre', 'name', required=True))
            if not code or not name:
                raise ValueError('Centro %s necesita Codigo y Nombre.' % index)
            if code in clean and clean[code] != name:
                raise ValueError('Código de centro duplicado con nombres diferentes: %s' % code)
            clean[code] = name
        existing = {rec.code: rec for rec in Center.search([
            ('company_id', '=', company.id), ('code', 'in', list(clean)),
        ])}
        counts = {'created': 0, 'updated': 0, 'unchanged': 0}
        for code, name in clean.items():
            rec = existing.get(code)
            if not rec:
                Center.create({'company_id': company.id, 'code': code, 'name': name})
                counts['created'] += 1
            elif rec.name != name:
                rec.write({'name': name})
                counts['updated'] += 1
            else:
                counts['unchanged'] += 1
        return counts

    @api.model
    def _normalize_consumption(self, item):
        code = as_text(get_value(item, 'Codigo', 'codigo_cuenta', required=True))
        center = as_text(get_value(item, 'Centro', 'codigo_centro_costo'))
        subcenter = as_text(get_value(item, 'Subcentro', 'codigo_subcentro'))
        date = parse_erp_date(get_value(item, 'Fecha', required=True))
        amount = parse_amount(get_value(item, 'Valor', required=True))
        external_id = as_text(get_value(item, 'id', 'external_id', 'id_movimiento'))
        return code, center, subcenter, date, amount, external_id

    @api.model
    def _sync_consumptions(self, company, rows, api_record):
        """Upsert determinista; no DUPLICAR cuando reenvían el mismo lote.

        Si no hay ID externo se utiliza hash de la tupla completa, con ordinal
        para movimientos idénticos. Sin un ID ERP, importes corregidos pueden
        aparecer como un nuevo movimiento (no se pueden inferir reemplazos).
        """
        Expense = self.env['expense.budget.expense'].sudo().with_company(company)
        Account = self.env['expense.budget.account'].sudo().with_company(company)
        Center = self.env['expense.budget.cost.center'].sudo().with_company(company)
        normalized = [self._normalize_consumption(row) for row in rows]
        account_codes = {row[0] for row in normalized}
        center_codes = {row[1] for row in normalized if row[1]}
        accounts = {rec.code: rec for rec in Account.search([
            ('company_id', '=', company.id), ('code', 'in', list(account_codes)),
        ])}
        missing = account_codes - accounts.keys()
        if missing:
            raise ValueError('Cuentas aún no existentes: %s. Sincronice primero el catálogo.' %
                             ', '.join(sorted(missing)[:20]))
        centers = {rec.code: rec for rec in Center.search([
            ('company_id', '=', company.id), ('code', 'in', list(center_codes)),
        ])}
        # Algunos consumos usan centros ausentes del catálogo recibido. Conservar
        # esos códigos y evitar pérdidas; getcentrocostos actualizará su nombre.
        for code in sorted(center_codes - centers.keys()):
            centers[code] = Center.create({
                'company_id': company.id, 'code': code,
                'name': '%s (pendiente de catálogo)' % code,
            })
        duplicates = defaultdict(int)
        prepared = []
        for code, center_code, subcenter, when, amount, external_id in normalized:
            canonical_amount = str(Decimal(str(amount)).quantize(Decimal('0.01')))
            key_material = '|'.join((code, center_code, subcenter, when.isoformat(), canonical_amount))
            if external_id:
                key = 'erp:' + external_id
            else:
                duplicates[key_material] += 1
                key = 'erp-fingerprint:' + hashlib.sha256(
                    ('%s|%s' % (key_material, duplicates[key_material])).encode('utf-8')
                ).hexdigest()
            prepared.append((key, code, center_code, subcenter, when, amount))
        if len({item[0] for item in prepared}) != len(prepared):
            raise ValueError('La API devolvió identificadores de consumos duplicados.')
        counts = {'created': 0, 'updated': 0, 'unchanged': 0}
        for key, code, center_code, subcenter, when, amount in prepared:
            center = centers.get(center_code)
            data = {
                'Codigo': code, 'Valor': amount, 'Fecha': when.isoformat(),
                'Centro': center_code, 'Subcentro': subcenter,
                'Descripcion': 'Consumo ERP %s / %s' % (code, center_code or 'Sin centro'),
            }
            outcome = Expense._upsert_external(
                company, data, 'api', key, api_record=api_record,
            )
            counts[outcome] += 1
        return counts

    @api.model
    def _sync_company(self, company):
        company.ensure_one()
        config = self.env['expense.budget.api.config'].sudo().search([
            ('company_id', '=', company.id),
        ], limit=1)
        result = {'created': 0, 'updated': 0, 'unchanged': 0, 'errors': 0, 'apis': 0}
        if not config:
            return result
        chosen = (
            ('accounts', config.account_api_id),
            ('centers', config.center_catalog_api_id),
            ('consumptions', config.consumption_api_id),
        )
        for kind, api_record in chosen:
            if not api_record:
                continue
            result['apis'] += 1
            counts = {'created': 0, 'updated': 0, 'unchanged': 0}
            try:
                with self.env.cr.savepoint():
                    rows = self._call(company, api_record, kind)
                    if kind == 'accounts':
                        counts = self._sync_accounts(company, rows)
                    elif kind == 'centers':
                        counts = self._sync_centers(company, rows)
                    else:
                        counts = self._sync_consumptions(company, rows, api_record)
                for name in counts:
                    result[name] += counts[name]
                self.env['expense.budget.sync.log'].sudo().create({
                    'company_id': company.id, 'api_administrator_id': api_record.id,
                    'status': 'success', 'created_count': counts['created'],
                    'updated_count': counts['updated'], 'unchanged_count': counts['unchanged'],
                    'message': '%s: sincronización terminada.' % ENDPOINTS[kind],
                })
            except Exception as exc:
                result['errors'] += 1
                _logger.exception('Error sincronizando %s para empresa %s', kind, company.id)
                self.env['expense.budget.sync.log'].sudo().create({
                    'company_id': company.id, 'api_administrator_id': api_record.id,
                    'status': 'error', 'message': ('%s: %s' % (kind, exc))[:1000],
                })
                # No consultar consumos con catálogos incompletos.
                if kind in ('accounts', 'centers'):
                    break
        return result

    @api.model
    def _notification(self, result):
        return {
            'type': 'ir.actions.client', 'tag': 'display_notification',
            'params': {
                'title': _('Sincronización de cuentas, centros y consumos'),
                'message': _('APIs: %(apis)s; creados: %(created)s; actualizados: %(updated)s; '
                             'sin cambios: %(unchanged)s; errores: %(errors)s.') % result,
                'type': 'warning' if result['errors'] else 'success',
                'sticky': bool(result['errors']),
            },
        }

    @api.model
    def cron_sync_every_5h(self):
        """Solo sincroniza empresas con endpoints configurados; cron ejecutado como root."""
        Config = self.env['expense.budget.api.config'].sudo()
        for config in Config.search([]):
            if not (config.account_api_id or config.center_catalog_api_id or config.consumption_api_id):
                continue
            self._sync_company(config.company_id)
