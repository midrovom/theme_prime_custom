# -*- coding: utf-8 -*-
"""Sincronización de catálogo de centros desde una API ya creada."""
import logging
from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError, UserError
from .expense import get_value, as_text

_logger = logging.getLogger(__name__)


class ExpenseBudgetCostCenterAPIConfig(models.Model):
    _name = 'expense.budget.cost.center.api.config'
    _description = 'API existente para centros de costo'
    _rec_name = 'company_id'
    _check_company_auto = True

    company_id = fields.Many2one('res.company', string='Empresa', required=True,
                                 default=lambda self: self.env.company, index=True)
    api_administrator_id = fields.Many2one(
        'api.administrator', string='API de centros de costo', required=True,
        ondelete='restrict', check_company=True,
        domain="[('company_id', '=', company_id), ('type', '=', 'get'), ('status', '=', 'A')]",
    )
    _sql_constraints = [
        ('cc_api_company_uniq', 'unique(company_id)',
         'Solo puede configurar una API de centros de costo por empresa.'),
    ]

    @api.constrains('company_id', 'api_administrator_id')
    def _check_api(self):
        for record in self:
            api_rec = record.api_administrator_id
            if api_rec.company_id != record.company_id or api_rec.type != 'get' or api_rec.status != 'A':
                raise ValidationError(_('Seleccione una API GET activa de la misma empresa.'))

    def action_sync(self):
        if not self.env.user.has_group('expense_budget_control.group_expense_budget_manager'):
            raise AccessError(_('Solo el administrador puede sincronizar desde esta configuración.'))
        self.ensure_one()
        result = self.env['expense.budget.cost.center.sync']._sync_company(self.company_id)
        return self.env['expense.budget.cost.center.sync']._notification(result)


class ExpenseBudgetCostCenterSync(models.AbstractModel):
    _name = 'expense.budget.cost.center.sync'
    _description = 'Sincronización de centros de costo por API Administrator'

    @api.model
    def _extract_rows(self, response):
        if isinstance(response, dict):
            if response.get('success') is False:
                raise ValueError(as_text(response.get('message')) or 'La API reportó un error.')
            rows = response.get('data', response.get('items', response.get('centros_costo')))
            if isinstance(rows, dict):
                nested = next((rows[key] for key in ('centros_costo', 'cost_centers', 'items')
                               if key in rows), None)
                rows = nested if nested is not None else [rows]
        else:
            rows = response
        if not isinstance(rows, list):
            raise ValueError('La API debe devolver data como lista de centros de costo.')
        if len(rows) > 50000:
            raise ValueError('Máximo de 50.000 centros por sincronización.')
        return rows

    @api.model
    def _sync_company(self, company):
        company.ensure_one()
        config = self.env['expense.budget.cost.center.api.config'].sudo().search([
            ('company_id', '=', company.id),
        ], limit=1)
        totals = {'created': 0, 'updated': 0, 'unchanged': 0, 'errors': 0, 'apis': 0}
        if not config:
            return totals
        selected = config.api_administrator_id
        if not selected or selected.status != 'A' or selected.type != 'get' or selected.company_id != company:
            raise UserError(_('La API de centros de costo no está activa o pertenece a otra empresa.'))
        totals['apis'] = 1
        try:
            with self.env.cr.savepoint():
                response = self.env['api.administrator'].sudo().call_api(
                    selected.name, method='get', company_id=company.id,
                )
                centers = self._extract_rows(response)
                Center = self.env['expense.budget.cost.center'].sudo().with_company(company)
                # Validación completa de lote antes de modificar datos.
                values = []
                seen = set()
                for index, row in enumerate(centers, start=1):
                    if not isinstance(row, dict):
                        raise ValueError('Centro %s no es objeto JSON.' % index)
                    code = as_text(get_value(row, 'code', 'codigo', 'codigo_centro_costo',
                                             'cost_center_code', 'Code', required=True))
                    name = as_text(get_value(row, 'name', 'nombre', 'centro_costo',
                                             'cost_center_name', required=True))
                    if not code or not name:
                        raise ValueError('Centro %s requiere código y nombre.' % index)
                    api_company = as_text(get_value(row, 'company_id', 'empresa'))
                    if api_company and api_company.casefold() not in {
                        company.name.casefold(), str(company.id), (company.display_name or '').casefold()
                    }:
                        raise ValueError('Centro %s pertenece a empresa %s, no %s.' % (
                            code, api_company, company.name,
                        ))
                    if code in seen:
                        raise ValueError('Código %s duplicado en la respuesta API.' % code)
                    seen.add(code)
                    values.append((code, name))
                existing = {rec.code: rec for rec in Center.search([
                    ('company_id', '=', company.id), ('code', 'in', [code for code, _ in values]),
                ])}
                for code, name in values:
                    rec = existing.get(code)
                    if rec:
                        if rec.name != name:
                            rec.write({'name': name})
                            totals['updated'] += 1
                        else:
                            totals['unchanged'] += 1
                    else:
                        Center.create({'code': code, 'name': name, 'company_id': company.id})
                        totals['created'] += 1
            self.env['expense.budget.sync.log'].sudo().create({
                'company_id': company.id, 'api_administrator_id': selected.id,
                'status': 'success', 'created_count': totals['created'],
                'updated_count': totals['updated'], 'unchanged_count': totals['unchanged'],
                'message': 'Centros de costo: sincronización completada.',
            })
        except Exception as exc:
            _logger.exception('Error al sincronizar centros de costo, API %s', selected.id)
            totals['errors'] += 1
            self.env['expense.budget.sync.log'].sudo().create({
                'company_id': company.id, 'api_administrator_id': selected.id,
                'status': 'error', 'message': ('Centros de costo: %s' % exc)[:1000],
            })
        return totals

    @api.model
    def _notification(self, result):
        return {
            'type': 'ir.actions.client', 'tag': 'display_notification',
            'params': {
                'title': _('Sincronización de centros de costo'),
                'message': _('Insertados: %(created)s; actualizados: %(updated)s; '
                             'sin cambios: %(unchanged)s; errores: %(errors)s.') % result,
                'type': 'warning' if result['errors'] else 'success',
                'sticky': bool(result['errors']),
            },
        }
