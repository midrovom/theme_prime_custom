# -*- coding: utf-8 -*-
import logging

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError

from .expense import get_value, as_text

_logger = logging.getLogger(__name__)


class APIAdministrator(models.Model):
    _inherit = 'api.administrator'

    is_expense_budget_sync = fields.Boolean(
        string='Sincronizar gastos presupuestarios', default=False,
        help='Activa la importación de movimientos de gastos desde esta API.',
    )

    def button_run_sync(self):
        """Respeta el comportamiento original de stock cuando no es API de gastos."""
        for record in self:
            if record.is_expense_budget_sync:
                if not self.env.user.has_group('expense_budget_control.group_expense_budget_manager'):
                    raise AccessError(_('Requiere el grupo Administrador de presupuestos de gastos.'))
                result = self.env['expense.budget.api.sync']._sync_company(
                    record.company_id, api_records=record,
                )
                return self.env['expense.budget.api.sync']._notification(result)
        return super().button_run_sync()


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
        domain = [
            ('company_id', '=', company.id),
            ('type', '=', 'get'),
            ('status', '=', 'A'),
            ('is_expense_budget_sync', '=', True),
        ]
        records = api_records.sudo().filtered_domain(domain) if api_records is not None else Admin.search(domain)
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
        Admin = self.env['api.administrator'].sudo()
        companies = Admin.search([
            ('type', '=', 'get'), ('status', '=', 'A'), ('is_expense_budget_sync', '=', True),
        ]).mapped('company_id')
        for company in companies:
            self._sync_company(company)
