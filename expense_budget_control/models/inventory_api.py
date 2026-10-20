# -*- coding: utf-8 -*-
"""Tres endpoints ERP: catálogo de cuentas, centros y consumos.

No almacena credenciales nuevas: usa exclusivamente api.administrator. No elimina
movimientos ausentes de respuestas sucesivas, que podrían ser consultas parciales.
"""
from collections import defaultdict
from datetime import datetime, timedelta
from decimal import Decimal
from time import monotonic
from psycopg2.extras import execute_values
from urllib.parse import urlsplit
from psycopg2 import IntegrityError, errorcodes
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
    """Fechas ERP tipo `abr 25 2026 ...` sin 4 intentos fallidos de strptime.

    La respuesta trae muchos años: este parser se ejecuta una vez por fila.
    Se conservan los formatos ISO y DD/MM/AAAA usados por el módulo.
    """
    value = as_text(value)
    parts = value.split()
    if len(parts) >= 3:
        month = SPANISH_MONTHS.get(parts[0].lower().strip('.'))
        if month:
            try:
                return datetime(int(parts[2]), month, int(parts[1])).date()
            except ValueError:
                pass
    for fmt in ('%Y-%m-%d', '%Y-%m-%d %H:%M:%S', '%d/%m/%Y', '%d-%m-%Y'):
        try:
            return datetime.strptime(value, fmt).date()
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
        started = monotonic()
        response = self.env['api.administrator'].sudo().call_api(
            record.name, method='get', company_id=company.id,
        )
        received = monotonic()
        rows = self._rows(response)
        _logger.info('[PRESUPUESTOS ERP] Respuesta endpoint=%s filas=%s empresa_id=%s '
                     'http=%.2fs parseo=%.2fs', ENDPOINTS[kind], len(rows), company.id,
                     received - started, monotonic() - received)
        return rows

    @api.model
    def _catalog_table(self, Model):
        """Las únicas tablas admitidas para upsert idempotente de catálogos ERP."""
        tables = {
            'expense.budget.account': 'expense_budget_account',
            'expense.budget.cost.center': 'expense_budget_cost_center',
        }
        table = tables.get(Model._name)
        if not table:
            raise ValueError('Modelo de catálogo no admitido: %s' % Model._name)
        return table

    @api.model
    def _find_catalog_record(self, Model, company, code):
        """Búsqueda por SQL contra empresa/código, incluyendo inactivos.

        La consulta del ORM puede devolver un resultado obsoleto cuando hay
        inserciones del cron y del formulario en la misma transacción. SQL
        lee los valores efectivos y busca primero una coincidencia exacta;
        la búsqueda por BTRIM recoge códigos heredados con espacios.
        """
        code = as_text(code)
        table = self._catalog_table(Model)
        self.env.cr.execute(
            'SELECT id FROM %s WHERE company_id = %%s AND BTRIM(code) = %%s '
            'ORDER BY CASE WHEN code = %%s THEN 0 ELSE 1 END, id LIMIT 2' % table,
            (company.id, code, code),
        )
        matches = [row[0] for row in self.env.cr.fetchall()]
        if len(matches) > 1:
            _logger.warning(
                '[PRESUPUESTOS ERP] Código con varias variantes históricas: '
                'modelo=%s empresa=%s código=%s registros=%s',
                Model._name, company.id, code, matches,
            )
        return Model.browse(matches[0]) if matches else Model.browse()

    @api.model
    def _upsert_catalog_record(self, Model, company, code, name, placeholder=False, existing=None):
        """Upsert por (empresa,código), sin violar índices únicos existentes.

        PostgreSQL ON CONFLICT DO NOTHING soporta incluso el caso en que otro
        proceso ya insertó la misma cuenta/centro. Se usa exclusivamente en
        los dos catálogos sencillos del módulo; la edición de registros
        existentes sigue pasando por ORM para respetar sus validaciones.
        """
        code, name = as_text(code), as_text(name)
        if not code or not name:
            raise ValueError('El código y el nombre del catálogo son obligatorios.')
        table = self._catalog_table(Model)
        record = self._find_catalog_record(Model, company, code)
        if not record and existing and existing.exists() and as_text(existing.code) == code:
            record = existing
        created = False
        collided = False
        if not record:
            self.env.cr.execute(
                'INSERT INTO %s '
                '(company_id, code, name, active, create_uid, create_date, write_uid, write_date) '
                'VALUES (%%s, %%s, %%s, TRUE, %%s, NOW(), %%s, NOW()) '
                'ON CONFLICT (company_id, code) DO NOTHING RETURNING id' % table,
                (company.id, code, name, self.env.uid, self.env.uid),
            )
            inserted = self.env.cr.fetchone()
            if inserted:
                # Al escribir con SQL invalidar cachés ORM para que los campos
                # y dominios posteriores vean inmediatamente el nuevo registro.
                Model.invalidate_model(['company_id', 'code', 'name', 'active'], flush=False)
                record = Model.browse(inserted[0])
                created = True
            else:
                record = self._find_catalog_record(Model, company, code)
                if not record:
                    raise UserError(_(
                        'Se detectó una cuenta o centro duplicado (%s), '
                        'pero no fue posible recuperar el registro existente.'
                    ) % code)
                collided = True
                _logger.info(
                    '[PRESUPUESTOS ERP] Código ya insertado por otra ejecución: '
                    'modelo=%s empresa=%s código=%s id=%s',
                    Model._name, company.id, code, record.id,
                )
        if created:
            return record, 'created', collided
        # Si se localizó un registro con espacios, normalizar su código,
        # siempre que no haya aparecido una versión exacta en paralelo.
        updates = {}
        if record.code != code:
            exact = Model.search([
                ('company_id', '=', company.id), ('code', '=', code),
            ], limit=1)
            if exact and exact != record:
                record = exact
            else:
                updates['code'] = code
        if not record.active:
            updates['active'] = True
        if not placeholder and record.name != name:
            updates['name'] = name
        if updates:
            try:
                with self.env.cr.savepoint():
                    record.write(updates)
                    record.flush_recordset(list(updates))
            except IntegrityError as exc:
                if exc.pgcode != errorcodes.UNIQUE_VIOLATION:
                    raise
                replacement = self._find_catalog_record(Model, company, code)
                if not replacement or replacement == record:
                    raise
                record = replacement
                collided = True
                safe_updates = {}
                if not record.active:
                    safe_updates['active'] = True
                if not placeholder and record.name != name:
                    safe_updates['name'] = name
                if safe_updates:
                    record.write(safe_updates)
                    record.flush_recordset(list(safe_updates))
            return record, 'updated', collided
        return record, 'unchanged', collided

    @api.model
    def _sync_catalog_batch(self, Model, company, rows, kind):
        """Actualizar el catálogo en lotes, sin una consulta por código.

        Solo se cambian nombres distintos y registros inactivos. Conserva
        vínculos rubro/cuentas y los campos editados ajenos al catálogo ERP.
        Las variantes históricas con espacios se delegan al upsert original.
        """
        clean = {}
        for index, item in enumerate(rows, 1):
            code = as_text(get_value(item, 'Codigo', 'code', required=True))
            name = as_text(get_value(item, 'Nombre', 'name', required=True))
            if not code or not name:
                raise ValueError('%s %s necesita Codigo y Nombre.' % (kind, index))
            if code in clean and clean[code] != name:
                raise ValueError('Código de %s repetido con distintos nombres: %s' % (kind, code))
            clean[code] = name
        counts = {'created': 0, 'updated': 0, 'unchanged': 0, 'reused_conflicts': 0}
        if not clean:
            return counts
        table = self._catalog_table(Model)
        # Leer la empresa una sola vez: también detecta códigos históricos
        # almacenados con espacios a la izquierda/derecha.
        self.env.cr.execute('SELECT id, code FROM %s WHERE company_id = %%s' % table,
                            (company.id,))
        legacy = {}
        for record_id, stored_code in self.env.cr.fetchall():
            normalized = as_text(stored_code)
            if normalized != stored_code and normalized in clean:
                legacy.setdefault(normalized, record_id)
        fast = dict(clean)
        for code, record_id in legacy.items():
            # No crear un código exacto si ya existe uno histórico con espacios.
            # La normalización individual conserva la protección de unicidad.
            self.env.cr.execute('SELECT 1 FROM %s WHERE company_id = %%s AND code = %%s' % table,
                                (company.id, code))
            if self.env.cr.fetchone():
                continue
            _rec, outcome, collided = self._upsert_catalog_record(
                Model, company, code, clean[code], existing=Model.browse(record_id),
            )
            counts[outcome] += 1
            counts['reused_conflicts'] += int(collided)
            fast.pop(code, None)
        # Una sentencia por bloque de 500 sustituye las búsquedas/escrituras
        # por registro. ON CONFLICT solo actualiza cambios reales.
        values = [(company.id, code, name, self.env.uid, self.env.uid)
                  for code, name in fast.items()]
        query = """INSERT INTO %s AS target
            (company_id, code, name, active, create_uid, create_date, write_uid, write_date)
            VALUES %%s
            ON CONFLICT (company_id, code) DO UPDATE SET
                name = EXCLUDED.name,
                active = TRUE,
                write_uid = EXCLUDED.write_uid,
                write_date = NOW()
            WHERE target.name IS DISTINCT FROM EXCLUDED.name
               OR target.active IS DISTINCT FROM TRUE
            RETURNING (xmax = 0) AS was_created""" % table
        template = '(%s, %s, %s, TRUE, %s, NOW(), %s, NOW())'
        batch_created = batch_updated = 0
        for pos in range(0, len(values), 500):
            result = execute_values(self.env.cr, query, values[pos:pos + 500],
                                    template=template, fetch=True)
            batch_created += sum(bool(row[0]) for row in result)
            batch_updated += sum(not bool(row[0]) for row in result)
        counts['created'] += batch_created
        counts['updated'] += batch_updated
        counts['unchanged'] += len(values) - batch_created - batch_updated
        # Insert/UPDATE SQL no pasa por write() del ORM: invalidar caché.
        Model.invalidate_model(['name', 'code', 'active'], flush=False)
        return counts

    @api.model
    def _sync_accounts(self, company, rows):
        Model = self.env['expense.budget.account'].sudo().with_company(company).with_context(active_test=False)
        return self._sync_catalog_batch(Model, company, rows, 'Cuenta')

    @api.model
    def _sync_centers(self, company, rows):
        Model = self.env['expense.budget.cost.center'].sudo().with_company(company).with_context(active_test=False)
        return self._sync_catalog_batch(Model, company, rows, 'Centro')

    @api.model
    def _sync_subcenters(self, company, rows):
        """Catálogo seleccionable desde TODOS los años devueltos por el ERP.

        No mezcla centros con el mismo subcentro. Al sincronizar un presupuesto
        antiguo se incluyen sus códigos en el selector, aunque el cron habitual
        importe los consumos monetarios del año vigente.
        """
        combinations = set()
        for item in rows:
            # Para catalogar subcentros no es necesario convertir Fecha/Valor
            # de todos los años: basta con los códigos del propio JSON.
            center_code = as_text(get_value(item, 'Centro', 'codigo_centro_costo'))
            subcenter = as_text(get_value(item, 'Subcentro', 'codigo_subcentro')).upper()
            if center_code and subcenter:
                combinations.add((center_code, subcenter))
        if not combinations:
            return {'created': 0, 'unchanged': 0}
        Center = self.env['expense.budget.cost.center'].sudo().with_company(company).with_context(active_test=False)
        Subcenter = self.env['expense.budget.subcenter'].sudo().with_company(company)
        center_codes = sorted({center for center, _sub in combinations})
        centers = {rec.code.strip(): rec for rec in Center.search([
            ('company_id', '=', company.id), ('code', 'in', center_codes),
        ])}
        for code in center_codes:
            if code not in centers:
                center_rec, _state, _conflict = self._upsert_catalog_record(
                    Center, company, code, '%s (pendiente de catálogo)' % code,
                    placeholder=True,
                )
                centers[code] = center_rec
        known = {(rec.center_id.id, rec.code): rec for rec in Subcenter.search([
            ('company_id', '=', company.id),
            ('center_id', 'in', [rec.id for rec in centers.values()]),
        ])}
        count = {'created': 0, 'unchanged': 0}
        to_create = []
        for center_code, subcenter_code in sorted(combinations):
            center_rec = centers[center_code]
            key = (center_rec.id, subcenter_code)
            if key in known:
                count['unchanged'] += 1
            else:
                to_create.append({'company_id': company.id, 'center_id': center_rec.id,
                                  'code': subcenter_code})
        for pos in range(0, len(to_create), 250):
            Subcenter.create(to_create[pos:pos + 250])
            count['created'] += len(to_create[pos:pos + 250])
        _logger.info('[PRESUPUESTOS ERP] Subcentros: nuevos=%s existentes=%s empresa=%s',
                     count['created'], count['unchanged'], company.id)
        return count

    @api.model
    def _normalize_consumption(self, item, known_date=None):
        code = as_text(get_value(item, 'Codigo', 'codigo_cuenta', required=True))
        center = as_text(get_value(item, 'Centro', 'codigo_centro_costo'))
        subcenter = as_text(get_value(item, 'Subcentro', 'codigo_subcentro')).upper()
        date = known_date if known_date is not None else parse_erp_date(
            get_value(item, 'Fecha', required=True))
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
        # La API devuelve todos los años. No convertir importes, generar hashes
        # ni validar cuentas de movimientos fuera del año seleccionado.
        relevant = []
        for row in rows:
            when = parse_erp_date(get_value(row, 'Fecha', required=True))
            if when.year == year:
                relevant.append(self._normalize_consumption(row, known_date=when))
        counts = {'created': 0, 'updated': 0, 'unchanged': 0,
                  'received': len(rows), 'skipped': len(rows)-len(relevant),
                  'linked': 0, 'unmatched': 0, 'reused_conflicts': 0, 'placeholder_accounts': 0,
                  'placeholder_centers': 0}
        if not relevant:
            return counts
        account_codes = {row[0] for row in relevant}
        center_codes = {row[1] for row in relevant if row[1]}
        existing_accounts = {rec.code: rec for rec in Account.search([
            ('company_id', '=', company.id), ('code', 'in', list(account_codes)),
        ])}
        accounts = {}
        for code in sorted(account_codes):
            rec = existing_accounts.get(code)
            if rec and rec.active:
                accounts[code] = rec
                continue
            rec, outcome, collided = self._upsert_catalog_record(
                Account, company, code, '%s (pendiente de catálogo)' % code,
                placeholder=True, existing=rec,
            )
            accounts[code] = rec
            if outcome == 'created':
                counts['placeholder_accounts'] += 1
            counts['reused_conflicts'] += int(collided)
        existing_centers = {rec.code: rec for rec in Center.search([
            ('company_id', '=', company.id), ('code', 'in', list(center_codes)),
        ])}
        centers = {}
        for code in sorted(center_codes):
            rec = existing_centers.get(code)
            if rec and rec.active:
                centers[code] = rec
                continue
            rec, outcome, collided = self._upsert_catalog_record(
                Center, company, code, '%s (pendiente de catálogo)' % code,
                placeholder=True, existing=rec,
            )
            centers[code] = rec
            if outcome == 'created':
                counts['placeholder_centers'] += 1
            counts['reused_conflicts'] += int(collided)
        # Preparar todas las claves primero para hacer una sola búsqueda por
        # lote en vez de una búsqueda de movimiento por cada fila recibida.
        duplicates = defaultdict(int)
        prepared = []
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
            prepared.append((code, center_code, subcenter, when, amount, key,
                             'api:%s:%s' % (api_record.id, key)))
        # Una búsqueda de proyecciones para todo el año evita una consulta SQL
        # por cada cuenta/centro/subcentro/mes detectado en la respuesta.
        Line = self.env['expense.budget.line'].sudo()
        budget_lines = Line.search([
            ('budget_id.company_id', '=', company.id),
            ('budget_id.year', '=', year),
            ('account_id', 'in', [rec.id for rec in accounts.values()]),
        ], order='id')
        line_index = {}
        for line in budget_lines:
            key = (line.account_id.id, line.cost_center_id.id or False,
                   int(line.month), as_text(line.subcenter_code).upper())
            line_index.setdefault(key, line.id)

        # Leer los campos de gastos existentes en bloques con SQL, sin
        # construir un recordset ni ejecutar write() si el gasto no cambió.
        all_keys = list({row[6] for row in prepared})
        existing = {}
        for pos in range(0, len(all_keys), 500):
            self.env.cr.execute("""SELECT id, source_key, account_id, cost_center_id, subcenter_code,
                       date, amount, description, reference, api_administrator_id,
                       budget_line_id
                FROM expense_budget_expense
                WHERE company_id = %s AND source_key = ANY(%s)""",
                (company.id, all_keys[pos:pos + 500]),
            )
            existing.update({rec[1]: rec for rec in self.env.cr.fetchall()})

        pending_creates = {}
        # keys duplicadas con el mismo id explícito en una sola respuesta:
        # conservar el último valor, sin crear varias filas con la misma clave.
        duplicate_keys = 0
        for code, center_code, subcenter, when, amount, key, source_key in prepared:
            account = accounts[code]
            center = centers[center_code] if center_code else Center.browse()
            prefix = (account.id, center.id or False, when.month)
            line_id = (
                (line_index.get((*prefix, subcenter)) if subcenter else None)
                or line_index.get((*prefix, ''))
                or False
            )
            description = 'Consumo ERP %s / %s / %s' % (
                code, center_code or 'Sin centro', subcenter or 'Sin subcentro')
            values = {
                'company_id': company.id, 'account_id': account.id,
                'cost_center_id': center.id or False,
                'subcenter_code': subcenter or False,
                'date': fields.Date.to_string(when), 'amount': amount,
                'description': description, 'reference': False,
                'source': 'api', 'source_key': source_key,
                'api_administrator_id': api_record.id,
                'budget_line_id': line_id,
            }
            if line_id:
                counts['linked'] += 1
            else:
                counts['unmatched'] += 1
            if source_key in pending_creates:
                pending_creates[source_key] = values
                duplicate_keys += 1
                continue
            old = existing.get(source_key)
            if not old:
                pending_creates[source_key] = values
                continue
            (_old_id, _key, old_account, old_center, old_subcenter, old_date,
             old_amount, old_description, old_reference, old_api, old_line) = old
            identical = (
                old_account == values['account_id'] and
                (old_center or False) == values['cost_center_id'] and
                as_text(old_subcenter).upper() == as_text(values['subcenter_code']).upper() and
                old_date == when and
                abs(float(old_amount or 0) - float(amount)) < 0.0000001 and
                as_text(old_description) == description and
                (old_reference or False) == values['reference'] and
                (old_api or False) == api_record.id and
                (old_line or False) == line_id
            )
            if identical:
                counts['unchanged'] += 1
            else:
                # Solo para cambios reales reutilizar el método de escritura
                # original, con validaciones y reconciliación de línea.
                row = {'Codigo': code, 'Valor': amount, 'Fecha': when.isoformat(),
                       'Centro': center_code, 'Subcentro': subcenter,
                       'Descripcion': description}
                outcome = Expense._upsert_external(
                    company, row, 'api', key, api_record=api_record,
                    resolved_account=account, resolved_center=center,
                    resolved_line=Line.browse(line_id),
                    known_existing=Expense.browse(old[0]),
                )
                counts[outcome] += 1
        # batch create() activa los cómputos de Consumido en lotes, en vez
        # de una creación por cada movimiento del histórico.
        all_new = list(pending_creates.values())
        for pos in range(0, len(all_new), 200):
            Expense.create(all_new[pos:pos + 200])
        counts['created'] += len(all_new)
        counts['unchanged'] += duplicate_keys
        return counts

    @api.model
    def _rows_for_saved_lines(self, rows, lines):
        """Filtrar el historial completo *antes* de convertir importes o consultar SQL.

        El ERP devuelve todos los años. Índice en memoria por Código/Centro
        y un único search de líneas evitan N búsquedas SQL por movimiento.
        Se conserva la prioridad de subcentro exacto sobre línea general.
        """
        lines = lines.exists().filtered(lambda rec: rec.account_id and rec.month)
        if not lines:
            return []
        selected = defaultdict(set)
        account_centers = {}
        for line in lines:
            key = (as_text(line.account_id.code), as_text(line.cost_center_id.code),
                   int(line.budget_id.year), int(line.month))
            selected[key].add(line.id)
            account_centers[key] = (line.account_id.id, line.cost_center_id.id or False)
        pairs = {(key[0], key[1]) for key in selected}
        company = lines[0].company_id
        candidates = self.env['expense.budget.line'].sudo().search([
            ('budget_id.company_id', '=', company.id),
            ('budget_id.year', 'in', list({key[2] for key in selected})),
            ('account_id', 'in', list({rec.account_id.id for rec in lines})),
            ('month', 'in', list({str(key[3]) for key in selected})),
        ])
        by_subcenter = {}
        for line in candidates:
            key = (line.account_id.id, line.cost_center_id.id or False,
                   int(line.budget_id.year), int(line.month),
                   (line.subcenter_code or '').strip().upper())
            by_subcenter.setdefault(key, line.id)
        result = []
        for item in rows:
            code = as_text(get_value(item, 'Codigo', 'codigo_cuenta'))
            center = as_text(get_value(item, 'Centro', 'codigo_centro_costo'))
            # Descartar la gran mayoría del histórico sin convertir Fecha/Valor.
            if (code, center) not in pairs:
                continue
            when = parse_erp_date(get_value(item, 'Fecha', required=True))
            key = (code, center, when.year, when.month)
            if key not in selected:
                continue
            account_id, center_id = account_centers[key]
            sub = as_text(get_value(item, 'Subcentro', 'codigo_subcentro')).upper()
            index = (account_id, center_id, when.year, when.month)
            target_id = (
                by_subcenter.get((*index, sub))
                or by_subcenter.get((*index, ''))
            )
            if target_id in selected[key]:
                result.append(item)
        return result

    @api.model
    def _reconcile_saved_line_periods(self, lines):
        """Revisar vinculaciones históricas antes y después de consultar el ERP.

        Una importación antigua pudo enlazar un movimiento a un mes distinto.
        Se recorren tanto los gastos actualmente enlazados a la proyección
        como los que *deberían* corresponder a su Código/Centro/Año/Mes, y se
        calcula otra vez la línea mediante la fecha real del gasto.
        No se modifica el movimiento ni su importe ni su fecha.
        """
        from datetime import date
        Expense = self.env['expense.budget.expense'].sudo()
        processed = set()
        corrected = 0
        for line in lines.exists():
            if not line.account_id or not line.month:
                continue
            year, month = int(line.budget_id.year), int(line.month)
            start = date(year, month, 1)
            end = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
            period = [
                ('date', '>=', fields.Date.to_string(start)),
                ('date', '<', fields.Date.to_string(end)),
            ]
            # OR(expenses linked to this line, expenses matching the period).
            # Odoo normalizes this implicit AND with the explicit '&' operands.
            period_filter = [
                ('company_id', '=', line.company_id.id),
                ('account_id', '=', line.account_id.id),
                ('cost_center_id', '=', line.cost_center_id.id or False),
            ] + period
            domain = ['|', ('budget_line_id', '=', line.id),
                      *(['&'] * (len(period_filter) - 1)), *period_filter]
            for expense in Expense.search(domain):
                if expense.id in processed:
                    continue
                processed.add(expense.id)
                target = Expense._find_budget_line(
                    expense.company_id.id, expense.account_id.id, expense.date,
                    expense.cost_center_id.id or False, expense.subcenter_code,
                )
                if expense.budget_line_id != target:
                    expense.write({'budget_line_id': target.id or False})
                    corrected += 1
        if corrected:
            _logger.info('[PRESUPUESTOS ERP] Gastos reconciliados por fecha real: %s', corrected)
        return corrected

    @api.model
    def _sync_saved_lines(self, lines):
        """Obtener Consumido al guardar con preferencia por datos ya sincronizados.

        Guardar Proyectado nunca llama al ERP (se filtra desde budget/line.write).
        Si el cron/manual ya importó el año completo recientemente o la línea
        se consultó hace poco, enlazar gastos locales toma precedencia.
        La primera consulta de un período todavía no sincronizado sí consulta
        getconsumosgastos/2 y guarda la respuesta para futuras aperturas.
        """
        lines = lines.exists().filtered(lambda line: line.account_id and line.month)
        if not lines:
            return
        grouped = defaultdict(lambda: self.env['expense.budget.line'])
        for line in lines:
            grouped[(line.company_id.id, int(line.budget_id.year))] |= line
        for (company_id, year), group in grouped.items():
            company = self.env['res.company'].browse(company_id)
            now = datetime.utcnow()
            recently_checked = now - timedelta(minutes=30)
            # Siempre enlazar gastos previamente importados, incluso si no
            # se necesita red. La fecha real evita mezclar otros meses.
            self._reconcile_saved_line_periods(group)
            pending = group.filtered(
                lambda line: not line.erp_checked_at or
                fields.Datetime.to_datetime(line.erp_checked_at) < recently_checked
            )
            if not pending:
                _logger.info('[PRESUPUESTOS ERP] Guardar rápido: %s líneas en caché local (año=%s)',
                             len(group), year)
                continue
            api_rec = False
            counts = {}
            try:
                config = self.env['expense.budget.api.config'].sudo().search([
                    ('company_id', '=', company.id),
                ], limit=1)
                api_rec = self._choose_api(company, config, 'consumptions')
                if not api_rec:
                    _logger.info('[PRESUPUESTOS ERP] No hay API de consumo para empresa=%s', company.id)
                    continue
                # La sincronización completa manual o programada trae TODOS los
                # registros del año. Si está fresca, ya están en Gastos reales.
                full_sync = self.env['expense.budget.sync.log'].sudo().search([
                    ('company_id', '=', company.id),
                    ('api_administrator_id', '=', api_rec.id),
                    ('status', '=', 'success'),
                    ('year', '=', year),
                    ('create_date', '>=', fields.Datetime.to_string(now - timedelta(hours=5))),
                    ('message', 'ilike', 'OK:'),
                ], limit=1)
                if full_sync:
                    pending.sudo().with_context(skip_expense_budget_consumption_on_save=True).write({
                        'erp_checked_at': fields.Datetime.now(),
                    })
                    _logger.info('[PRESUPUESTOS ERP] Guardar rápido: año=%s ya sincronizado; '
                                 'sin segunda llamada HTTP. empresa=%s líneas=%s',
                                 year, company.id, len(pending))
                    continue
                with self.env.cr.savepoint():
                    self.env.cr.execute('SELECT pg_advisory_xact_lock(%s, %s)', (484700, company.id))
                    all_rows = self._call(company, api_rec, 'consumptions')
                    selected_rows = self._rows_for_saved_lines(all_rows, pending)
                    # Subcentros de otros años ya se importan en el cron/manual;
                    # al guardar, limitar inserciones a los períodos pedidos.
                    if selected_rows:
                        self._sync_subcenters(company, selected_rows)
                    counts = self._sync_consumptions(company, selected_rows, api_rec, year)
                    counts['reconciled'] = self._reconcile_saved_line_periods(pending)
                    counts['received'] = len(all_rows)
                    counts['skipped'] = len(all_rows) - len(selected_rows)
                    pending.sudo().with_context(skip_expense_budget_consumption_on_save=True).write({
                        'erp_checked_at': fields.Datetime.now(),
                    })
                    detail = (
                        'Guardar proyección: recibidos=%s, coincidentes=%s, '
                        'nuevos=%s, actualizados=%s, sin_cambios=%s, '
                        'vinculados=%s, reconciliados=%s, periodos=%s' % (
                            len(all_rows), len(selected_rows), counts.get('created', 0),
                            counts.get('updated', 0), counts.get('unchanged', 0),
                            counts.get('linked', 0), counts.get('reconciled', 0),
                            ', '.join(sorted({'%04d-%02d' % (int(line.budget_id.year), int(line.month))
                                              for line in pending})),
                        )
                    )
                    self._save_log(company, api_rec, year, 'consumptions', 'success', detail, counts)
                    _logger.info('[PRESUPUESTOS ERP] %s | empresa=%s año=%s', detail, company.id, year)
            except Exception as exc:
                if getattr(exc, 'pgcode', None) in (
                    errorcodes.SERIALIZATION_FAILURE, errorcodes.DEADLOCK_DETECTED,
                ):
                    raise
                _logger.exception('[PRESUPUESTOS ERP] ERROR consultando consumos al guardar '
                                  'empresa=%s año=%s: %s', company.id, year, exc)
                self._save_log(
                    company, api_rec, year, 'consumptions', 'error',
                    'Guardar proyección: no fue posible consultar consumos: %s' % str(exc)[:1500],
                )

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
        # Un único trabajo ERP por empresa a la vez (incluye botón y cron).
        # Bloqueo transaccional PostgreSQL: se libera automáticamente al
        # terminar, incluso si la importación falla. No requiere migración.
        self.env.cr.execute('SELECT pg_advisory_xact_lock(%s, %s)', (484700, company.id))
        _logger.info('[PRESUPUESTOS ERP] Bloqueo de sincronización adquirido empresa=%s', company.id)
        year = int(year or fields.Date.context_today(self).year)
        if not 2000 <= year <= 2100:
            raise UserError(_('El año de sincronización debe estar entre 2000 y 2100.'))
        config = self.env['expense.budget.api.config'].sudo().search([
            ('company_id', '=', company.id),
        ], limit=1)
        result = {'created': 0, 'updated': 0, 'unchanged': 0,
                  'errors': 0, 'apis': 0, 'year': year, 'details': []}
        total_started = monotonic()
        for kind in ('accounts', 'centers', 'consumptions'):
            phase_started = monotonic()
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
                    api_finished = monotonic()
                    if kind == 'accounts':
                        counts = self._sync_accounts(company, rows)
                    elif kind == 'centers':
                        counts = self._sync_centers(company, rows)
                    else:
                        counts = self._sync_consumptions(company, rows, api_rec, year)
                        subcenter_stats = self._sync_subcenters(company, rows)
                        counts['subcenters_created'] = subcenter_stats['created']
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
                           'cuentas_pendientes=%s centros_pendientes=%s subcentros_nuevos=%s duplicados_recuperados=%s' % (
                               counts.get('received', 0), counts.get('created', 0),
                               counts.get('updated', 0), counts.get('unchanged', 0),
                               counts.get('skipped', 0), counts.get('linked', 0),
                               counts.get('unmatched', 0), counts.get('placeholder_accounts', 0),
                               counts.get('placeholder_centers', 0), counts.get('subcenters_created', 0),
                               counts.get('reused_conflicts', 0)))
                api_seconds = api_finished - phase_started
                import_seconds = monotonic() - api_finished
                message += ' tiempo_api=%.2fs tiempo_guardado=%.2fs' % (api_seconds, import_seconds)
                self._save_log(company, api_rec, year, kind, 'success', message, counts)
                _logger.info('[PRESUPUESTOS ERP] %s | empresa=%s año=%s | %s',
                             ENDPOINTS[kind], company.id, year, message)
                result['details'].append('%s: %s filas (%s nuevas, %s vinculadas, %s omitidas, %s subcentros nuevos · HTTP %.1fs · Odoo %.1fs)' % (
                    kind, counts['received'], counts.get('created', 0),
                    counts.get('linked', 0), counts.get('skipped', 0),
                    counts.get('subcenters_created', 0), api_seconds, import_seconds))
            except Exception as exc:
                _logger.error('[PRESUPUESTOS ERP] Fase %s terminó con error tras %.2fs',
                              kind, monotonic() - phase_started)
                if getattr(exc, 'pgcode', None) in (
                    errorcodes.SERIALIZATION_FAILURE, errorcodes.DEADLOCK_DETECTED,
                ):
                    # No registrar 3 errores ni confirmar un resultado parcial:
                    # Odoo reintentará automáticamente la petición con una
                    # nueva transacción/snapshot, igual que en el ORM nativo.
                    _logger.warning('[PRESUPUESTOS ERP] Conflicto concurrente en %s; '
                                    'reintentar transacción completa (empresa=%s)',
                                    ENDPOINTS[kind], company.id)
                    raise
                result['errors'] += 1
                safe_message = str(exc)[:1500]
                _logger.exception('[PRESUPUESTOS ERP] ERROR endpoint=%s empresa=%s año=%s: %s',
                                  ENDPOINTS[kind], company.id, year, safe_message)
                self._save_log(company, api_rec, year, kind, 'error', safe_message, counts)
                result['details'].append('%s: ERROR %s' % (kind, safe_message[:180]))
        _logger.info('[PRESUPUESTOS ERP] Tiempo total empresa=%s año=%s: %.2fs',
                     company.id, year, monotonic() - total_started)
        return result

    @api.model
    def _notification(self, result, show_year=True):
        details = ' | '.join(result.get('details', []))
        message = ('APIs consultadas: %(apis)s · Nuevos: %(created)s · '
                   'Actualizados: %(updated)s · Ya existentes: %(unchanged)s · '
                   'Errores: %(errors)s' % result)
        if show_year:
            message = ('Año %s · ' % result['year']) + message
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
