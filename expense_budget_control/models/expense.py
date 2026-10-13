# -*- coding: utf-8 -*-
from datetime import datetime, date
from decimal import Decimal, InvalidOperation
import math
import re
import unicodedata

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError


def normalized_key(value):
    text = unicodedata.normalize('NFKD', str(value or ''))
    text = ''.join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r'[^a-z0-9]+', '_', text.lower()).strip('_')


def get_value(mapping, *aliases, required=False):
    normalized = {normalized_key(key): value for key, value in mapping.items()}
    for alias in aliases:
        value = normalized.get(normalized_key(alias))
        if value is not None and str(value).strip() != '':
            return value
    if required:
        raise ValueError('Campo obligatorio ausente: %s' % ' / '.join(aliases))
    return None


def as_text(value):
    if value is None:
        return ''
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def parse_amount(value):
    if isinstance(value, bool) or value is None or str(value).strip() == '':
        raise ValueError('El monto está vacío o es inválido.')
    value = str(value).strip().replace(' ', '').replace('\u00a0', '')
    if ',' in value and '.' in value:
        value = value.replace('.', '').replace(',', '.') if value.rfind(',') > value.rfind('.') else value.replace(',', '')
    elif ',' in value:
        value = value.replace(',', '.')
    try:
        amount = float(Decimal(value))
    except (InvalidOperation, ValueError, OverflowError) as exc:
        raise ValueError('Monto numérico inválido: %s' % value) from exc
    if not math.isfinite(amount):
        raise ValueError('El monto no puede ser infinito o NaN.')
    return amount


def parse_expense_date(value):
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    value = as_text(value)
    for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y'):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    raise ValueError('Fecha inválida: %s (use AAAA-MM-DD o DD/MM/AAAA).' % value)


class ExpenseBudgetExpense(models.Model):
    _name = 'expense.budget.expense'
    _description = 'Movimiento real de gastos'
    _order = 'date desc, id desc'
    _check_company_auto = True

    date = fields.Date(string='Fecha', required=True, index=True,
                       default=fields.Date.context_today)
    company_id = fields.Many2one('res.company', string='Empresa', required=True,
                                 default=lambda self: self.env.company, index=True)
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id', store=True)
    account_id = fields.Many2one('expense.budget.account', string='Cuenta controlada',
                                 required=True, ondelete='restrict', check_company=True, index=True)
    category_id = fields.Many2one('expense.budget.category', related='account_id.category_id',
                                  store=True, string='Rubro', index=True)
    budget_line_id = fields.Many2one('expense.budget.line', string='Línea presupuestaria',
                                     ondelete='set null', index=True, check_company=True,
                                     readonly=True, copy=False)
    amount = fields.Monetary(string='Gasto real', required=True, currency_field='currency_id',
                             help='Positivo = gasto; negativo = reverso/devolución.')
    description = fields.Char(string='Descripción', required=True)
    reference = fields.Char(string='Referencia')
    source = fields.Selection([('manual', 'Manual'), ('excel', 'Excel'), ('api', 'API')],
                              string='Origen', required=True, default='manual', readonly=True)
    source_key = fields.Char(string='Clave externa', copy=False, index=True, readonly=True,
                             help='Identificador único del sistema de origen.')
    api_administrator_id = fields.Many2one('api.administrator', string='Configuración API',
                                          ondelete='set null', readonly=True, copy=False)

    _sql_constraints = [
        ('source_key_company_unique', 'unique(company_id, source_key)',
         'Este movimiento externo ya fue importado para la empresa.'),
    ]

    @api.constrains('account_id', 'company_id', 'budget_line_id', 'date')
    def _check_consistency(self):
        for rec in self:
            if rec.account_id.company_id != rec.company_id:
                raise ValidationError(_('La cuenta de gasto debe pertenecer a la empresa.'))
            line = rec.budget_line_id
            if line and (line.account_id != rec.account_id or
                         line.company_id != rec.company_id or
                         line.budget_id.year != rec.date.year or
                         int(line.month) != rec.date.month):
                raise ValidationError(_('La línea presupuestaria no corresponde a la cuenta/mes/empresa del gasto.'))

    @api.model
    def _find_budget_line(self, company_id, account_id, expense_date):
        expense_date = fields.Date.to_date(expense_date)
        if not expense_date or not company_id or not account_id:
            return self.env['expense.budget.line']
        # Hay varios presupuestos posibles por empresa/año: localizar la
        # cuenta y el mes directamente, sin tomar el primer presupuesto.
        return self.env['expense.budget.line'].search([
            ('budget_id.company_id', '=', company_id),
            ('budget_id.year', '=', expense_date.year),
            ('account_id', '=', account_id),
            ('month', '=', str(expense_date.month)),
        ], limit=1)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            company_id = vals.get('company_id') or self.env.company.id
            date_value = vals.get('date') or fields.Date.context_today(self)
            account_id = vals.get('account_id')
            if account_id:
                vals['budget_line_id'] = self._find_budget_line(company_id, account_id, date_value).id or False
        return super().create(vals_list)

    def write(self, vals):
        changed = {'account_id', 'company_id', 'date'}
        if changed.intersection(vals):
            for rec in self:
                record_vals = dict(vals)
                record_vals['budget_line_id'] = self._find_budget_line(
                    vals.get('company_id', rec.company_id.id),
                    vals.get('account_id', rec.account_id.id),
                    vals.get('date', rec.date),
                ).id or False
                super(ExpenseBudgetExpense, rec).write(record_vals)
            return True
        return super().write(vals)

    @api.model
    def _upsert_external(self, company, data, source, external_id, api_record=None):
        if source not in ('api', 'excel') or not as_text(external_id):
            raise ValueError('El identificador externo es obligatorio para Excel y API.')
        code = as_text(get_value(data, 'codigo_cuenta', 'cuenta', 'codigo', 'account_code', required=True))
        account = self.env['expense.budget.account'].search([
            ('company_id', '=', company.id), ('code', '=', code),
        ], limit=1)
        if not account:
            raise ValueError('La cuenta %s no existe en el catálogo de la empresa %s.' % (code, company.name))
        expense_date = parse_expense_date(get_value(data, 'fecha', 'date', required=True))
        amount = parse_amount(get_value(data, 'monto', 'importe', 'valor', 'amount', required=True))
        scope = ('api:%s:' % api_record.id) if source == 'api' else 'excel:'
        external_key = scope + as_text(external_id)
        values = {
            'company_id': company.id,
            'account_id': account.id,
            'date': fields.Date.to_string(expense_date),
            'amount': amount,
            'description': as_text(get_value(data, 'descripcion', 'detalle', 'concepto', 'description')) or
                           ('Gasto %s' % as_text(external_id)),
            'reference': as_text(get_value(data, 'referencia', 'documento', 'reference')) or False,
            'source': source,
            'source_key': external_key,
            'api_administrator_id': api_record.id if api_record else False,
        }
        existing = self.search([('company_id', '=', company.id), ('source_key', '=', external_key)], limit=1)
        if existing:
            updates = {}
            for key, value in values.items():
                if key in ('source', 'source_key'):
                    continue
                current = existing[key]
                if key in ('company_id', 'account_id', 'api_administrator_id'):
                    current = current.id or False
                elif key == 'date':
                    current = fields.Date.to_string(current)
                if current != value:
                    updates[key] = value
            if updates:
                existing.write(updates)
                return 'updated'
            return 'unchanged'
        self.create(values)
        return 'created'
