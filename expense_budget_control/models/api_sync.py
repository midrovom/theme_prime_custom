# -*- coding: utf-8 -*-
import logging

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError

from .expense import get_value, as_text

_logger = logging.getLogger(__name__)


class ExpenseBudgetAPIConfig(models.Model):
    _name = 'expense.budget.api.config'
    _description = 'Selección de API existente para gastos presupuestarios'
    _rec_name = 'company_id'
    _check_company_auto = True

    company_id = fields.Many2one(
        'res.company', string='Empresa', required=True, index=True,
        default=lambda self: self.env.company,
    )
    sync_year = fields.Integer(
        string='Año de los consumos (legado)', required=True,
        default=lambda self: fields.Date.context_today(self).year,
        help='Campo anterior conservado por compatibilidad; la sincronización manual usa el año actual. '
             'Desde un presupuesto se utiliza el año del presupuesto. '
             'El cron automático siempre usa el año actual.',
    )
    api_administrator_id = fields.Many2one(
        'api.administrator', string='API anterior (opcional)',
        ondelete='restrict', check_company=True,
        domain="[('company_id', '=', company_id), ('type', '=', 'get'), ('status', '=', 'A')]",
        help='Seleccione una API GET activa creada previamente en API Administrator.',
    )

    account_api_id = fields.Many2one(
        'api.administrator', string='API de cuentas de gastos',
        ondelete='restrict', check_company=True,
        domain="[('company_id', '=', company_id), ('type', '=', 'get'), ('status', '=', 'A')]",
        help='Endpoint: inventory_odoo/consulta_odoo/getctagastos/2',
    )
    center_catalog_api_id = fields.Many2one(
        'api.administrator', string='API de centros de costo (ERP)',
        ondelete='restrict', check_company=True,
        domain="[('company_id', '=', company_id), ('type', '=', 'get'), ('status', '=', 'A')]",
        help='Endpoint: inventory_odoo/consulta_odoo/getcentrocostos/2',
    )
    consumption_api_id = fields.Many2one(
        'api.administrator', string='API de consumos de gastos (ERP)',
        ondelete='restrict', check_company=True,
        domain="[('company_id', '=', company_id), ('type', '=', 'get'), ('status', '=', 'A')]",
        help='Endpoint: inventory_odoo/consulta_odoo/getconsumosgastos/2',
    )

    _sql_constraints = [
        ('expense_budget_api_company_unique', 'unique(company_id)',
         'Ya existe una API de gastos seleccionada para esta empresa.'),
    ]

    @api.constrains('company_id', 'api_administrator_id', 'account_api_id', 'center_catalog_api_id', 'consumption_api_id')
    def _check_selected_api(self):
        for record in self:
            selected = record.api_administrator_id
            if selected and selected.company_id != record.company_id:
                raise UserError(_('La API seleccionada debe pertenecer a la misma empresa.'))
            if selected and selected.type != 'get':
                raise UserError(_('Seleccione una API configurada como GET.'))
            for api_record in (record.account_api_id, record.center_catalog_api_id,
                               record.consumption_api_id):
                if api_record and (api_record.company_id != record.company_id or
                                   api_record.type != 'get' or api_record.status != 'A'):
                    raise UserError(_('Las APIs seleccionadas deben ser GET activas de la empresa.'))

    def action_sync(self):
        if not self.env.user.has_group('expense_budget_control.group_expense_budget_manager'):
            raise AccessError(_('Requiere el grupo Administrador de presupuestos de gastos.'))
        self.ensure_one()
        result = self.env['expense.budget.inventory.sync']._sync_company(
            self.company_id, year=fields.Date.context_today(self).year,
        )
        return self.env['expense.budget.inventory.sync']._notification(result, show_year=False)


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
    received_count = fields.Integer(string='Filas recibidas')
    skipped_count = fields.Integer(string='Omitidas por año')
    matched_count = fields.Integer(string='Vinculadas al presupuesto')
    unmatched_count = fields.Integer(string='Sin línea presupuestaria')
    year = fields.Integer(string='Año consultado')


class ExpenseBudgetAPISync(models.AbstractModel):
    _name = 'expense.budget.api.sync'
    _description = 'Servicio de importación de gastos desde API Administrator'

    @api.model
    def _extract_rows(self, response):
        if isinstance(response, dict):
            if response.get('success') is False:
                raise ValueError(as_text(response.get('message')) or 'La API reportó un error.')
            rows = response.get('data')
            if rows is None:
                rows = response.get('items')
            if rows is None:
                raise ValueError('La respuesta no tiene el arreglo data (ni items).')
        else:
            rows = response
        if not isinstance(rows, list):
            raise ValueError('La API debe responder con una lista JSON en data o items.')
        if len(rows) > 50000:
            raise ValueError('Máximo de 50.000 movimientos por sincronización.')
        return rows

    @api.model
    def _sync_company(self, company, api_records=None):
        """Interno: convocado desde botones protegidos o la tarea programada."""
        company.ensure_one()
        Admin = self.env['api.administrator'].sudo()
        # La API se define en API Administrator: aquí solo se selecciona su registro.
        selected = api_records if api_records is not None else self.env[
            'expense.budget.api.config'
        ].sudo().search([('company_id', '=', company.id)]).api_administrator_id
        domain = [
            ('company_id', '=', company.id),
            ('type', '=', 'get'),
            ('status', '=', 'A'),
        ]
        records = selected.sudo().filtered_domain(domain)
        total = {'created': 0, 'updated': 0, 'unchanged': 0, 'errors': 0, 'apis': len(records)}
        if not records:
            return total

        for config in records:
            counts = {'created': 0, 'updated': 0, 'unchanged': 0}
            try:
                # Un savepoint por API asegura que un lote con errores no quede a medias.
                with self.env.cr.savepoint():
                    result = Admin.call_api(config.name, method='get', company_id=company.id)
                    data = self._extract_rows(result)
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
                    'message': 'Sincronización completada.',
                })
                for key in counts:
                    total[key] += counts[key]
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
        return {
            'type': 'ir.actions.client', 'tag': 'display_notification',
            'params': {
                'title': _('Sincronización de gastos'),
                'message': message,
                'type': 'warning' if result['errors'] else 'success',
                'sticky': bool(result['errors']),
            },
        }

    @api.model
    def cron_sync_all(self):
        """Tarea opcional: la instalación la deja desactivada por seguridad."""
        companies = self.env['expense.budget.api.config'].sudo().search([]).mapped('company_id')
        center_companies = self.env['expense.budget.cost.center.api.config'].sudo().search([]).mapped('company_id')
        for company in (companies | center_companies):
            self.env['expense.budget.cost.center.sync']._sync_company(company)
            self._sync_company(company)
