# -*- coding: utf-8 -*-
"""Tres endpoints ERP: catálogo de cuentas, centros y consumos.

No almacena credenciales nuevas: usa exclusivamente api.administrator. No elimina
movimientos ausentes de respuestas sucesivas, que podrían ser consultas parciales.
"""
from collections import defaultdict
from datetime import datetime
from decimal import Decimal
from urllib.parse import urlsplit
import hashlib
import logging

from odoo import api, fields, models, _
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
        """Acepta respuesta lista, {data:[...]}, o envoltorios data/result/items."""
        current = response
        for _depth in range(5):
            if isinstance(current, list):
                if len(current) > 100000:
                    raise ValueError('Límite de 100.000 filas por consulta.')
                if any(not isinstance(row, dict) for row in current):
                    raise ValueError('Todos los registros deben ser objetos JSON.')
                return current
            if not isinstance(current, dict):
                break
            if current.get('success') is False:
                raise ValueError(as_text(current.get('message')) or 'La API devolvió success=false.')
            for key in ('data', 'items', 'result', 'cuentas', 'centros', 'registros', 'Data'):
                if key in current and current[key] is not None:
                    current = current[key]
                    break
            else:
                if get_value(current, 'Codigo', 'code'):
                    return [current]
                break
        raise ValueError('Respuesta JSON sin lista de registros (data/items/result).')

    @api.model
    def _matches_endpoint(self, api_record, kind):
        """Valida ruta, admitiendo URL completa, barra final y parámetros GET."""
        path = as_text(api_record.end_point)
        path = urlsplit(path).path.strip('/').lower()
        wanted = ENDPOINTS[kind].lower()
        return path == wanted or path.endswith('/' + wanted)

    @api.model
    def _choose_api(self, company, config, kind):
        selected = {
            'accounts': 'account_api_id',
            'centers': 'center_catalog_api_id',
            'consumptions': 'consumption_api_id',
        }
        configured = config[selected[kind]] if config else False
        if configured:
            self._validate_api(company, configured, kind)
            return configured
        # Si el usuario no seleccionó las APIs, intentar localizarlas entre
        # las ya creadas en API Administrator, SIN crear endpoints adicionales.
        candidates = self.env['api.administrator'].sudo().search([
            ('company_id', '=', company.id), ('type', '=', 'get'), ('status', '=', 'A'),
        ])
        matches = candidates.filtered(lambda api_rec: self._matches_endpoint(api_rec, kind))
        if len(matches) > 1:
            raise UserError(_(
                'Se encontraron varias APIs para %(path)s. Seleccione una en Configuración API ERP.'
            ) % {'path': ENDPOINTS[kind]})
        return matches[:1]

    @api.model
    def _validate_api(self, company, record, kind):
        if not record:
            return False
        if record.company_id != company or record.type != 'get' or record.status != 'A':
            raise UserError(_('La API de %s debe ser GET, activa y de la misma empresa.') % kind)
        if not self._matches_endpoint(record, kind):
            raise UserError(_('La API de %(kind)s debe apuntar a %(path)s.') % {
                'kind': kind, 'path': ENDPOINTS[kind],
            })
        return True

    @api.model
    def _call(self, company, record, kind):
        self._validate_api(company, record, kind)
        _logger.info(
            '[PRESUPUESTOS ERP] Solicitando endpoint=%s empresa_id=%s api_id=%s',
            ENDPOINTS[kind], company.id, record.id,
        )
        response = self.env['api.administrator'].sudo().call_api(
            record.name, method='get', company_id=company.id,
        )
        rows = self._rows(response)
        _logger.info('[PRESUPUESTOS ERP] Respuesta endpoint=%s filas=%s empresa_id=%s',
                     ENDPOINTS[kind], len(rows), company.id)
        return rows

    @api.model
    def _sync_accounts(self, company, rows):
        Account = self.env['expense.budget.account'].sudo().with_company(company).with_context(active_test=False)
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
            elif rec.name != name or not rec.active:
                rec.write({'name': name, 'active': True})
                counts['updated'] += 1
            else:
                counts['unchanged'] += 1
        return counts

    @api.model
    def _sync_centers(self, company, rows):
        Center = self.env['expense.budget.cost.center'].sudo().with_company(company).with_context(active_test=False)
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
            elif rec.name != name or not rec.active:
                rec.write({'name': name, 'active': True})
                counts['updated'] += 1
            else:
                counts['unchanged'] += 1
        return counts

    @api.model
    def _normalize_consumption(self, item):
        code = as_text(get_value(item, 'Codigo', 'codigo_cuenta', required=True))
        center = as_text(get_value(item, 'Centro', 'codigo_centro_costo'))
        subcenter = as_text(get_value(item, 'Subcentro', 'codigo_subcentro')).upper()
        date = parse_erp_date(get_value(item, 'Fecha', required=True))
        amount = parse_amount(get_value(item, 'Valor', required=True))
        external_id = as_text(get_value(item, 'id', 'external_id', 'id_movimiento'))
        return code, center, subcenter, date, amount, external_id

    @api.model
    def _sync_consumptions(self, company, rows, api_record, year):
        """Importa solo el año pedido. Vincula por empresa/cuenta/centro/subcentro/mes.

        La huella no es un ID contable: sin ID del ERP no se pueden detectar
        rectificaciones en importe/fecha. Nunca mezcla años o empresas.
        """
        Expense = self.env['expense.budget.expense'].sudo().with_company(company)
        Account = self.env['expense.budget.account'].sudo().with_company(company).with_context(active_test=False)
        Center = self.env['expense.budget.cost.center'].sudo().with_company(company).with_context(active_test=False)
        normalized = [self._normalize_consumption(row) for row in rows]
        relevant = [row for row in normalized if row[3].year == year]
        counts = {'created': 0, 'updated': 0, 'unchanged': 0,
                  'received': len(rows), 'skipped': len(rows)-len(relevant),
                  'linked': 0, 'unmatched': 0, 'placeholder_accounts': 0,
                  'placeholder_centers': 0}
        if not relevant:
            return counts
        account_codes = {row[0] for row in relevant}
        center_codes = {row[1] for row in relevant if row[1]}
        accounts = {rec.code: rec for rec in Account.search([
            ('company_id', '=', company.id), ('code', 'in', list(account_codes)),
        ])}
        for code in sorted(account_codes - accounts.keys()):
            # No bloquear consumos reales si el catálogo llegó incompleto.
            # El catálogo actualizará el nombre en una próxima sincronización.
            accounts[code] = Account.create({
                'company_id': company.id, 'code': code,
                'name': '%s (pendiente de catálogo)' % code,
            })
            counts['placeholder_accounts'] += 1
        centers = {rec.code: rec for rec in Center.search([
            ('company_id', '=', company.id), ('code', 'in', list(center_codes)),
        ])}
        for code in sorted(center_codes - centers.keys()):
            centers[code] = Center.create({
                'company_id': company.id, 'code': code,
                'name': '%s (pendiente de catálogo)' % code,
            })
            counts['placeholder_centers'] += 1
        duplicates = defaultdict(int)
        for code, center_code, subcenter, when, amount, external_id in relevant:
            canonical_amount = str(Decimal(str(amount)).quantize(Decimal('0.01')))
            material = '|'.join((code, center_code, subcenter, when.isoformat(), canonical_amount))
            if external_id:
                key = 'erp:' + external_id
            else:
                duplicates[material] += 1
                key = 'erp-fingerprint:' + hashlib.sha256(
                    ('%s|%s' % (material, duplicates[material])).encode('utf-8')
                ).hexdigest()
            row = {
                'Codigo': code, 'Valor': amount, 'Fecha': when.isoformat(),
                'Centro': center_code, 'Subcentro': subcenter,
                'Descripcion': 'Consumo ERP %s / %s / %s' % (
                    code, center_code or 'Sin centro', subcenter or 'Sin subcentro'),
            }
            outcome = Expense._upsert_external(company, row, 'api', key, api_record=api_record)
            counts[outcome] += 1
            line = Expense._find_budget_line(company.id, accounts[code].id, when,
                                             centers[center_code].id if center_code else False,
                                             subcenter)
            if line:
                counts['linked'] += 1
            else:
                counts['unmatched'] += 1
        return counts

    @api.model
    def _save_log(self, company, api_record, year, kind, status, message, counts=None):
        counts = counts or {}
        self.env['expense.budget.sync.log'].sudo().create({
            'company_id': company.id,
            'api_administrator_id': api_record.id if api_record else False,
            'year': year,
            'status': status,
            'created_count': counts.get('created', 0),
            'updated_count': counts.get('updated', 0),
            'unchanged_count': counts.get('unchanged', 0),
            'received_count': counts.get('received', 0),
            'skipped_count': counts.get('skipped', 0),
            'matched_count': counts.get('linked', 0),
            'unmatched_count': counts.get('unmatched', 0),
            'message': ('[%s] %s' % (ENDPOINTS[kind], message))[:2000],
        })

    @api.model
    def _sync_company(self, company, year=None):
        """Una ejecución por empresa/año; cuentas -> centros -> consumos.

        Cada endpoint tiene su savepoint y log. Los errores no se ocultan
        tras una notificación 'sincronización completada'.
        """
        company.ensure_one()
        year = int(year or fields.Date.context_today(self).year)
        if not 2000 <= year <= 2100:
            raise UserError(_('El año de sincronización debe estar entre 2000 y 2100.'))
        config = self.env['expense.budget.api.config'].sudo().search([
            ('company_id', '=', company.id),
        ], limit=1)
        result = {'created': 0, 'updated': 0, 'unchanged': 0,
                  'errors': 0, 'apis': 0, 'year': year, 'details': []}
        for kind in ('accounts', 'centers', 'consumptions'):
            api_rec = False
            counts = {}
            try:
                api_rec = self._choose_api(company, config, kind)
                if not api_rec:
                    raise UserError(_(
                        'No hay una API GET activa para %s en esta empresa. '
                        'Créela en API Administrator y selecciónela en Configuración API ERP.'
                    ) % ENDPOINTS[kind])
                result['apis'] += 1
                with self.env.cr.savepoint():
                    rows = self._call(company, api_rec, kind)
                    if kind == 'accounts':
                        counts = self._sync_accounts(company, rows)
                    elif kind == 'centers':
                        counts = self._sync_centers(company, rows)
                    else:
                        counts = self._sync_consumptions(company, rows, api_rec, year)
                    counts.setdefault('received', len(rows))
                    # Una lista vacía no equivale a éxito cuando el usuario
                    # está esperando cuentas/centros/consumos desde el ERP.
                    if not rows:
                        _logger.warning('[PRESUPUESTOS ERP] Respuesta vacía: %s empresa=%s',
                                        ENDPOINTS[kind], company.id)
                for name in ('created', 'updated', 'unchanged'):
                    result[name] += counts.get(name, 0)
                message = ('OK: %s filas; creados=%s actualizados=%s sin_cambios=%s '
                           'omitidos_por_año=%s vinculados=%s sin_proyeccion=%s '
                           'cuentas_pendientes=%s centros_pendientes=%s' % (
                               counts.get('received', 0), counts.get('created', 0),
                               counts.get('updated', 0), counts.get('unchanged', 0),
                               counts.get('skipped', 0), counts.get('linked', 0),
                               counts.get('unmatched', 0), counts.get('placeholder_accounts', 0),
                               counts.get('placeholder_centers', 0)))
                self._save_log(company, api_rec, year, kind, 'success', message, counts)
                _logger.info('[PRESUPUESTOS ERP] %s | empresa=%s año=%s | %s',
                             ENDPOINTS[kind], company.id, year, message)
                result['details'].append('%s: %s filas (%s nuevas, %s vinculadas, %s omitidas)' % (
                    kind, counts['received'], counts.get('created', 0),
                    counts.get('linked', 0), counts.get('skipped', 0)))
            except Exception as exc:
                result['errors'] += 1
                safe_message = str(exc)[:1500]
                _logger.exception('[PRESUPUESTOS ERP] ERROR endpoint=%s empresa=%s año=%s: %s',
                                  ENDPOINTS[kind], company.id, year, safe_message)
                self._save_log(company, api_rec, year, kind, 'error', safe_message, counts)
                result['details'].append('%s: ERROR %s' % (kind, safe_message[:180]))
        return result

    @api.model
    def _notification(self, result):
        details = ' | '.join(result.get('details', []))
        message = ('Año %(year)s · APIs consultadas: %(apis)s · Nuevos: %(created)s · '
                   'Actualizados: %(updated)s · Errores: %(errors)s' % result)
        if details:
            message += '\n' + details
        return {
            'type': 'ir.actions.client', 'tag': 'display_notification',
            'params': {
                'title': _('Sincronización ERP: cuentas, centros y consumos'),
                'message': message,
                'type': 'warning' if result['errors'] else 'success',
                'sticky': bool(result['errors']),
            },
        }

    @api.model
    def cron_sync_every_5h(self):
        """Cada cinco horas: año actual, empresas con configuración o endpoints ERP.

        Descubrir endpoints GET activos evita que un cron silenciosamente no
        trabaje por no haberse creado aún la fila de configuración unificada.
        """
        configured = self.env['expense.budget.api.config'].sudo().search([])
        companies = configured.mapped('company_id')
        candidates = self.env['api.administrator'].sudo().search([
            ('type', '=', 'get'), ('status', '=', 'A'),
        ])
        for record in candidates:
            if any(self._matches_endpoint(record, kind) for kind in ENDPOINTS):
                companies |= record.company_id
        year = fields.Date.context_today(self).year
        for company in companies:
            self._sync_company(company, year=year)
