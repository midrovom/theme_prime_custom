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
    cost_center_id = fields.Many2one(
        'expense.budget.cost.center', string='Centro de costo',
        check_company=True, ondelete='restrict', index=True,
    )
    subcenter_code = fields.Char(
        string='Subcentro', index=True,
        help='Código Subcentro recibido de getconsumosgastos; se conserva para trazabilidad.',
    )
    budget_line_id = fields.Many2one('expense.budget.line', string='Línea presupuestaria',
                                     ondelete='set null', index=True, check_company=True,
                                     readonly=True, copy=False)
    # Monetary rounds amounts to currency precision (typically 2 decimals)
    # even before the budget can aggregate them. Keep the raw API amount.
    # min_display_digits only defines the MINIMUM visual precision.
    amount = fields.Float(string='Gasto real', required=True,
                          min_display_digits='Presupuesto de Gastos',
                          help='Importe original sin redondeo monetario. Positivo = gasto; negativo = reverso/devolución.')
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

    @api.constrains('account_id', 'company_id', 'cost_center_id', 'budget_line_id', 'date', 'subcenter_code')
    def _check_consistency(self):
        for rec in self:
            if rec.account_id.company_id != rec.company_id:
                raise ValidationError(_('La cuenta de gasto debe pertenecer a la empresa.'))
            if rec.cost_center_id and rec.cost_center_id.company_id != rec.company_id:
                raise ValidationError(_('El centro de costo debe pertenecer a la empresa del gasto.'))
            line = rec.budget_line_id
            if line and (line.cost_center_id != rec.cost_center_id or
                         line.account_id != rec.account_id or
                         line.company_id != rec.company_id or
                         line.budget_id.year != rec.date.year or
                         int(line.month) != rec.date.month):
                raise ValidationError(_('La línea presupuestaria no corresponde a la cuenta/mes/empresa del gasto.'))

    @api.model
    def _find_budget_line(self, company_id, account_id, expense_date,
                          cost_center_id=False, subcenter_code=False):
        expense_date = fields.Date.to_date(expense_date)
        if not expense_date or not company_id or not account_id:
            return self.env['expense.budget.line']
        domain = [
            ('budget_id.company_id', '=', company_id),
            ('budget_id.year', '=', expense_date.year),
            ('account_id', '=', account_id),
            ('cost_center_id', '=', cost_center_id or False),
            ('month', '=', str(expense_date.month)),
        ]
        Line = self.env['expense.budget.line'].sudo()
        # Subcentro se conserva solo para trazabilidad en gastos reales.
        # El presupuesto consume la primera línea de cuenta/centro/mes/año;
        # cualquier subcentro ERP contribuye al mismo valor mensual.
        return Line.search(domain, order='id', limit=1)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if 'subcenter_code' in vals:
                vals['subcenter_code'] = as_text(vals['subcenter_code']).upper() or False
            company_id = vals.get('company_id') or self.env.company.id
            date_value = vals.get('date') or fields.Date.context_today(self)
            account_id = vals.get('account_id')
            if account_id and 'budget_line_id' not in vals:
                vals['budget_line_id'] = self._find_budget_line(
                    company_id, account_id, date_value, vals.get('cost_center_id'), vals.get('subcenter_code')
                ).id or False
        return super().create(vals_list)

    def write(self, vals):
        if 'subcenter_code' in vals:
            vals = dict(vals, subcenter_code=as_text(vals['subcenter_code']).upper() or False)
        changed = {'account_id', 'company_id', 'date', 'cost_center_id', 'subcenter_code'}
        if changed.intersection(vals):
            for rec in self:
                record_vals = dict(vals)
                record_vals['budget_line_id'] = self._find_budget_line(
                    vals.get('company_id', rec.company_id.id),
                    vals.get('account_id', rec.account_id.id),
                    vals.get('date', rec.date),
                    vals.get('cost_center_id', rec.cost_center_id.id),
                    vals.get('subcenter_code', rec.subcenter_code),
                ).id or False
                super(ExpenseBudgetExpense, rec).write(record_vals)
            return True
        return super().write(vals)

    @api.model
    def _upsert_external(self, company, data, source, external_id, api_record=None,
                         resolved_account=None, resolved_center=None,
                         resolved_line=None, known_existing=None):
        if source not in ('api', 'excel') or not as_text(external_id):
            raise ValueError('El identificador externo es obligatorio para Excel y API.')
        code = as_text(get_value(data, 'codigo_cuenta', 'cuenta', 'codigo', 'account_code', required=True))
        account = resolved_account if resolved_account is not None else self.env['expense.budget.account'].search([
            ('company_id', '=', company.id), ('code', '=', code),
        ], limit=1)
        if not account:
            raise ValueError('La cuenta %s no existe en el catálogo de la empresa %s.' % (code, company.name))
        center_code = as_text(get_value(data, 'codigo_centro_costo', 'centro_costo',
                                         'cost_center_code', 'cost_center', 'Centro'))
        center = resolved_center if resolved_center is not None else self.env['expense.budget.cost.center']
        if center_code:
            if resolved_center is None:
                center = center.search([('company_id', '=', company.id), ('code', '=', center_code)], limit=1)
            if not center:
                raise ValueError('El centro de costo %s no existe para %s.' % (center_code, company.name))
        expense_date = parse_expense_date(get_value(data, 'fecha', 'date', required=True))
        amount = parse_amount(get_value(data, 'monto', 'importe', 'valor', 'amount', required=True))
        scope = ('api:%s:' % api_record.id) if source == 'api' else 'excel:'
        external_key = scope + as_text(external_id)
        values = {
            'company_id': company.id,
            'account_id': account.id,
            'cost_center_id': center.id or False,
            'subcenter_code': as_text(get_value(data, 'Subcentro', 'codigo_subcentro')).upper() or False,
            'date': fields.Date.to_string(expense_date),
            'amount': amount,
            'description': as_text(get_value(data, 'descripcion', 'detalle', 'concepto', 'description')) or
                           ('Gasto %s' % as_text(external_id)),
            'reference': as_text(get_value(data, 'referencia', 'documento', 'reference')) or False,
            'source': source,
            'source_key': external_key,
            'api_administrator_id': api_record.id if api_record else False,
        }
        # Reconciliar también registros ya importados en versiones previas.
        # Un gasto sin línea debe poder aparecer en Consumido tras crear
        # posteriormente la proyección mensual correspondiente.
        matched_line = resolved_line if resolved_line is not None else self._find_budget_line(
            company.id, account.id, expense_date, center.id or False,
            values['subcenter_code'],
        )
        values['budget_line_id'] = matched_line.id or False
        existing = known_existing if known_existing is not None else self.search([
            ('company_id', '=', company.id), ('source_key', '=', external_key),
        ], limit=1)
        if existing:
            updates = {}
            for key, value in values.items():
                if key in ('source', 'source_key'):
                    continue
                current = existing[key]
                if key in ('company_id', 'account_id', 'cost_center_id', 'api_administrator_id', 'budget_line_id'):
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
