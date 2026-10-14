# -*- coding: utf-8 -*-
import logging

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError

from .expense import get_value, as_text, normalized_key

_logger = logging.getLogger(__name__)


class ExpenseBudgetAPIConfig(models.Model):
    _name = 'expense.budget.api.config'
    _description = 'Selección de APIs existentes para gastos y catálogo'
    _rec_name = 'company_id'
    _check_company_auto = True

    company_id = fields.Many2one(
        'res.company', string='Empresa', required=True, index=True,
        default=lambda self: self.env.company,
    )
    api_administrator_id = fields.Many2one(
        'api.administrator', string='API existente', required=True,
        ondelete='restrict', check_company=True,
        domain="[('company_id', '=', company_id), ('type', '=', 'get'), ('status', '=', 'A')]",
        help='API de movimientos de gastos previamente creada en API Administrator.',
    )
    catalog_api_administrator_id = fields.Many2one(
        'api.administrator', string='API de rubros y cuentas',
        ondelete='restrict', check_company=True,
        domain="[('company_id', '=', company_id), ('type', '=', 'get'), ('status', '=', 'A')]",
        help='Opcional: seleccione una API GET existente que retorne rubros con sus cuentas. '
             'Si la API de gastos ya devuelve ese catálogo, no necesita seleccionarla de nuevo.',
    )

    _sql_constraints = [
        ('expense_budget_api_company_unique', 'unique(company_id)',
         'Ya existe una API de gastos seleccionada para esta empresa.'),
    ]

    @api.constrains('company_id', 'api_administrator_id', 'catalog_api_administrator_id')
    def _check_selected_api(self):
        for record in self:
            for selected in (record.api_administrator_id, record.catalog_api_administrator_id):
                if selected and selected.company_id != record.company_id:
                    raise UserError(_('La API seleccionada debe pertenecer a la misma empresa.'))
                if selected and selected.type != 'get':
                    raise UserError(_('Seleccione una API configurada como GET.'))

    def action_sync(self):
        if not self.env.user.has_group('expense_budget_control.group_expense_budget_manager'):
            raise AccessError(_('Requiere el grupo Administrador de presupuestos de gastos.'))
        self.ensure_one()
        # La sincronización ejecuta ambas APIs seleccionadas (si hay dos), sin
        # crear nuevas configuraciones en el módulo api_administrator.
        result = self.env['expense.budget.api.sync']._sync_company(self.company_id)
        return self.env['expense.budget.api.sync']._notification(result)


class ExpenseBudgetSyncLog(models.Model):
    _name = 'expense.budget.sync.log'
    _description = 'Historial de sincronización de gastos'
    _order = 'create_date desc, id desc'

    company_id = fields.Many2one('res.company', string='Empresa', required=True, index=True)
    api_administrator_id = fields.Many2one('api.administrator', string='API',
                                          ondelete='set null')
    status = fields.Selection([('success', 'Correcta'), ('error', 'Error')],
                              required=True, string='Estado')
    created_count = fields.Integer(string='Insertados')
    updated_count = fields.Integer(string='Actualizados')
    unchanged_count = fields.Integer(string='Sin cambios')
    message = fields.Text(string='Detalle')


class ExpenseBudgetAPISync(models.AbstractModel):
    _name = 'expense.budget.api.sync'
    _description = 'Servicio de importación de gastos y catálogo desde API Administrator'

    @api.model
    def _is_catalog_item(self, item):
        """No confundir un movimiento de gastos con un rubro y sus cuentas."""
        return (isinstance(item, dict)
                and bool(as_text(get_value(item, 'Code', 'codigo_rubro', 'rubro_codigo')))
                and bool(as_text(get_value(item, 'name', 'nombre', 'rubro')))
                and get_value(item, 'cuentas', 'accounts', 'cuentas_controladas',
                              'account_ids') is not None)

    @api.model
    def _extract_payload(self, response):
        """Acepta el JSON anterior de gastos y el nuevo catálogo en data."""
        if isinstance(response, dict):
            if response.get('success') is False:
                raise ValueError(as_text(response.get('message')) or 'La API reportó un error.')
            rows = response.get('data')
            if rows is None:
                rows = response.get('items')
            if rows is None:
                raise ValueError('La respuesta no tiene el campo data (ni items).')
        else:
            rows = response

        parent_company = None
        if isinstance(rows, dict):
            # Opcionalmente un solo objeto data o una envoltura con varios rubros.
            if self._is_catalog_item(rows):
                rows = [rows]
            else:
                parent_company = get_value(rows, 'company_id', 'empresa')
                batch = get_value(rows, 'rubros', 'categories')
                if not isinstance(batch, list):
                    raise ValueError('El objeto data debe incluir Code, name y cuentas '
                                     '(lista), o el arreglo rubros.')
                rows = batch
                if not rows:
                    return 'catalog', [], parent_company
                if not all(self._is_catalog_item(item) for item in rows):
                    raise ValueError('Cada rubro debe incluir Code, name y cuentas (lista).')
        if not isinstance(rows, list):
            raise ValueError('El campo data debe contener movimientos (lista) o rubros (objeto/lista).')
        if len(rows) > 50000:
            raise ValueError('Máximo de 50.000 registros por sincronización.')
        if not rows:
            return 'expense', [], parent_company
        detected = [self._is_catalog_item(item) for item in rows]
        if all(detected):
            return 'catalog', rows, parent_company
        if any(detected):
            raise ValueError('Una misma respuesta no puede mezclar gastos y rubros.')
        return 'expense', rows, parent_company

    @api.model
    def _extract_rows(self, response):
        """Compatibilidad con la interfaz previa usada para importar gastos."""
        _kind, rows, _parent_company = self._extract_payload(response)
        return rows

    @api.model
    def _validate_payload_company(self, company, company_identifier):
        if company_identifier is None or as_text(company_identifier) == '':
            return
        identifier = normalized_key(company_identifier)
        if identifier not in (normalized_key(company.name), str(company.id)):
            raise ValueError(
                'La empresa %s informada por la API no coincide con la empresa '
                'configurada (%s). Revise la selección en API Administrator.' %
                (as_text(company_identifier), company.name)
            )

    @api.model
    def _upsert_catalog(self, company, rows, parent_company=None):
        """Importación idempotente por (empresa, código), en una sola transacción.

        No borra rubros ni cuentas ausentes de la respuesta y nunca crea
        presupuestos o consumos. Conserva los identificadores existentes.
        """
        self._validate_payload_company(company, parent_company)
        Category = self.env['expense.budget.category'].sudo().with_company(company).with_context(active_test=False)
        Account = self.env['expense.budget.account'].sudo().with_company(company).with_context(active_test=False)
        result = {'rubros_created': 0, 'rubros_updated': 0, 'rubros_unchanged': 0,
                  'cuentas_created': 0, 'cuentas_updated': 0, 'cuentas_unchanged': 0}
        account_owners = {}
        account_count = 0

        for index, item in enumerate(rows, 1):
            if not self._is_catalog_item(item):
                raise ValueError('Rubro %s: Code, name y cuentas son obligatorios.' % index)
            self._validate_payload_company(
                company, get_value(item, 'company_id', 'empresa') or parent_company)
            rubro_code = as_text(get_value(item, 'Code', 'codigo_rubro', 'rubro_codigo', required=True))
            rubro_name = as_text(get_value(item, 'name', 'nombre', 'rubro', required=True))
            if not rubro_code or not rubro_name:
                raise ValueError('Rubro %s: el código y el nombre no pueden estar vacíos.' % index)
            accounts = get_value(item, 'cuentas', 'accounts', 'cuentas_controladas', 'account_ids')
            if not isinstance(accounts, list):
                raise ValueError('Rubro %s: cuentas debe ser una lista de objetos.' % rubro_code)

            category = Category.search([
                ('company_id', '=', company.id), ('code', '=', rubro_code),
            ], limit=1)
            if category:
                updates = {}
                if category.name != rubro_name:
                    updates['name'] = rubro_name
                if not category.active:
                    updates['active'] = True
                if updates:
                    category.write(updates)
                    result['rubros_updated'] += 1
                else:
                    result['rubros_unchanged'] += 1
            else:
                category = Category.create({
                    'company_id': company.id, 'code': rubro_code, 'name': rubro_name,
                })
                result['rubros_created'] += 1

            for number, entry in enumerate(accounts, 1):
                account_count += 1
                if account_count > 50000:
                    raise ValueError('Máximo de 50.000 cuentas por sincronización.')
                if not isinstance(entry, dict):
                    raise ValueError('Rubro %s, cuenta %s: se esperaba un objeto JSON.' %
                                     (rubro_code, number))
                account_code = as_text(get_value(entry, 'code', 'codigo', required=True))
                account_name = as_text(get_value(entry, 'name', 'nombre', required=True))
                if not account_code or not account_name:
                    raise ValueError('Rubro %s, cuenta %s: código y nombre obligatorios.' %
                                     (rubro_code, number))
                if account_code in account_owners and account_owners[account_code] != rubro_code:
                    raise ValueError('Cuenta %s duplicada en rubros distintos de la misma respuesta.' %
                                     account_code)
                account_owners[account_code] = rubro_code
                account = Account.search([
                    ('company_id', '=', company.id), ('code', '=', account_code),
                ], limit=1)
                if account:
                    changes = {}
                    if account.name != account_name:
                        changes['name'] = account_name
                    if account.category_id != category:
                        changes['category_id'] = category.id
                    if not account.active:
                        changes['active'] = True
                    if changes:
                        account.write(changes)
                        result['cuentas_updated'] += 1
                    else:
                        result['cuentas_unchanged'] += 1
                else:
                    Account.create({
                        'company_id': company.id, 'category_id': category.id,
                        'code': account_code, 'name': account_name,
                    })
                    result['cuentas_created'] += 1
        return result

    @api.model
    def _sync_company(self, company, api_records=None):
        """Interno: convocado desde botones protegidos o la tarea programada."""
        company.ensure_one()
        Admin = self.env['api.administrator'].sudo()
        if api_records is not None:
            selected = api_records
        else:
            settings = self.env['expense.budget.api.config'].sudo().search([
                ('company_id', '=', company.id)], limit=1)
            selected = settings.api_administrator_id | settings.catalog_api_administrator_id
        domain = [
            ('company_id', '=', company.id),
            ('type', '=', 'get'),
            ('status', '=', 'A'),
        ]
        records = selected.sudo().filtered_domain(domain)
        total = {'created': 0, 'updated': 0, 'unchanged': 0, 'errors': 0, 'apis': len(records),
                 'rubros_created': 0, 'rubros_updated': 0, 'rubros_unchanged': 0,
                 'cuentas_created': 0, 'cuentas_updated': 0, 'cuentas_unchanged': 0}
        if not records:
            return total

        for config in records:
            counts = {'created': 0, 'updated': 0, 'unchanged': 0}
            message = 'Sincronización completada.'
            extra = {}
            try:
                # Un savepoint por API asegura que un lote con errores no quede a medias.
                with self.env.cr.savepoint():
                    response = Admin.call_api(config.name, method='get', company_id=company.id)
                    kind, data, parent_company = self._extract_payload(response)
                    if kind == 'catalog':
                        extra = self._upsert_catalog(company, data, parent_company)
                        for name, count in extra.items():
                            outcome = name.rsplit('_', 1)[1]
                            counts[outcome] += count
                        message = ('Rubros: %s nuevos, %s actualizados, %s sin cambios. '
                                   'Cuentas: %s nuevas, %s actualizadas, %s sin cambios.') % (
                            extra['rubros_created'], extra['rubros_updated'],
                            extra['rubros_unchanged'], extra['cuentas_created'],
                            extra['cuentas_updated'], extra['cuentas_unchanged'])
                    else:
                        Expense = self.env['expense.budget.expense'].sudo().with_company(company)
                        for number, item in enumerate(data, start=1):
                            if not isinstance(item, dict):
                                raise ValueError('El movimiento %s no es un objeto JSON.' % number)
                            try:
                                external_id = get_value(
                                    item, 'id', 'identificador', 'external_id',
                                    'id_movimiento', 'idmovimiento', required=True,
                                )
                                outcome = Expense._upsert_external(
                                    company, item, 'api', external_id, api_record=config,
                                )
                            except (ValueError, UserError) as exc:
                                raise ValueError('Registro API %s: %s' % (number, exc)) from exc
                            counts[outcome] += 1
                self.env['expense.budget.sync.log'].sudo().create({
                    'company_id': company.id,
                    'api_administrator_id': config.id,
                    'status': 'success',
                    'created_count': counts['created'],
                    'updated_count': counts['updated'],
                    'unchanged_count': counts['unchanged'],
                    'message': message,
                })
                for key in counts:
                    total[key] += counts[key]
                for name, count in extra.items():
                    total[name] += count
            except Exception as exc:  # No exponer credenciales ni datos de respuesta en el log.
                _logger.exception('Error sincronizando presupuesto con API ID %s', config.id)
                total['errors'] += 1
                self.env['expense.budget.sync.log'].sudo().create({
                    'company_id': company.id,
                    'api_administrator_id': config.id,
                    'status': 'error',
                    'message': str(exc)[:1000],
                })
        return total

    @api.model
    def _notification(self, result):
        message = _('APIs: %(apis)s. Insertados: %(created)s, actualizados: %(updated)s, '
                    'sin cambios: %(unchanged)s, errores: %(errors)s.') % result
        if any(result.get(key) for key in ('rubros_created', 'rubros_updated',
                                           'cuentas_created', 'cuentas_updated')):
            message += (' Rubros: %s nuevos, %s actualizados. '
                        'Cuentas: %s nuevas, %s actualizadas.') % (
                result['rubros_created'], result['rubros_updated'],
                result['cuentas_created'], result['cuentas_updated'])
        return {
            'type': 'ir.actions.client', 'tag': 'display_notification',
            'params': {
                'title': _('Sincronización API'),
                'message': message,
                'type': 'warning' if result['errors'] else 'success',
                'sticky': bool(result['errors']),
            },
        }

    @api.model
    def cron_sync_all(self):
        """Tarea opcional: la instalación la deja desactivada por seguridad."""
        companies = self.env['expense.budget.api.config'].sudo().search([]).mapped('company_id')
        for company in companies:
            self._sync_company(company)
