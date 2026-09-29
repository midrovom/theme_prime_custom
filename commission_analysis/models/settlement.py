from collections import defaultdict

from psycopg2.extras import execute_values

from odoo import fields, models, _
from odoo.exceptions import UserError


class CommissionSettlementBatch(models.Model):
    _name = 'commission.settlement.batch'
    _description = 'Liquidación de Operador'
    _inherit = ['mail.thread']
    _order = 'id desc'

    name = fields.Char(
        default=lambda self: self.env['ir.sequence'].next_by_code('commission.settlement.batch'),
        required=True, copy=False,
    )
    operator_id = fields.Many2one('commission.operator', required=True, index=True)
    period = fields.Char(required=True)
    state = fields.Selection(
        [('draft', 'Borrador'), ('processed', 'Procesado'), ('closed', 'Cerrado')],
        default='draft', tracking=True,
    )
    line_ids = fields.One2many('commission.settlement.line', 'batch_id')
    file_ids = fields.One2many('commission.import.file', 'settlement_batch_id')
    line_count = fields.Integer(compute='_compute_totals', string='Registros')
    reported_total = fields.Monetary(compute='_compute_totals', string='Reportado')
    expected_total = fields.Monetary(compute='_compute_totals', string='Esperado')
    difference_total = fields.Monetary(compute='_compute_totals', string='Diferencia')
    currency_id = fields.Many2one(
        'res.currency', default=lambda self: self.env.company.currency_id.id
    )

    def _compute_totals(self):
        Line = self.env['commission.settlement.line']
        for rec in self:
            if not rec.id:
                rec.line_count = 0
                rec.reported_total = rec.expected_total = rec.difference_total = 0.0
                continue
            group = Line.read_group(
                [('batch_id', '=', rec.id)],
                ['reported_value:sum', 'expected_value:sum', 'difference:sum'],
                [],
            )
            values = group[0] if group else {}
            rec.line_count = Line.search_count([('batch_id', '=', rec.id)])
            rec.reported_total = values.get('reported_value', 0.0) or 0.0
            rec.expected_total = values.get('expected_value', 0.0) or 0.0
            rec.difference_total = values.get('difference', 0.0) or 0.0

    def action_recalculate(self):
        Line = self.env['commission.settlement.line']
        Sim = self.env['commission.sim']
        for batch in self:
            if batch.state == 'closed':
                raise UserError(_('No se puede recalcular una liquidación cerrada.'))
            last_id = 0
            affected_sim_ids = set()
            while True:
                lines = Line.search(
                    [('batch_id', '=', batch.id), ('id', '>', last_id)],
                    order='id', limit=5000,
                )
                if not lines:
                    break
                lines._recalculate_expected_bulk(batch=batch)
                affected_sim_ids.update(lines.mapped('sim_id').ids)
                last_id = lines[-1].id
            sim_ids = list(affected_sim_ids)
            for start in range(0, len(sim_ids), 10000):
                Sim._refresh_kpis(sim_ids[start:start + 10000])
        return True

    def action_close(self):
        self.write({'state': 'closed'})
        return True


class CommissionImportFile(models.Model):
    _name = 'commission.import.file'
    _description = 'Archivo Fuente Importado'
    _order = 'id desc'

    name = fields.Char(required=True)
    sha256 = fields.Char(required=True, index=True)
    attachment_id = fields.Many2one('ir.attachment', ondelete='set null')
    settlement_batch_id = fields.Many2one('commission.settlement.batch', ondelete='cascade')
    purchase_batch_id = fields.Many2one('commission.purchase.batch', ondelete='cascade')
    row_count = fields.Integer()
    imported_at = fields.Datetime(default=fields.Datetime.now)
    imported_by = fields.Many2one('res.users', default=lambda self: self.env.user)

    _sql_constraints = [
        ('sha_unique', 'unique(sha256)', 'Este archivo ya fue importado anteriormente.'),
    ]


class CommissionSettlementLine(models.Model):
    _name = 'commission.settlement.line'
    _description = 'Detalle de Comisión'
    _order = 'compensation_date desc, id desc'

    batch_id = fields.Many2one(
        'commission.settlement.batch', required=True, ondelete='cascade', index=True
    )
    operator_id = fields.Many2one(
        'commission.operator', related='batch_id.operator_id', store=True, index=True
    )
    sim_id = fields.Many2one('commission.sim', index=True, ondelete='set null')
    icc = fields.Char(index=True)
    icc_key = fields.Char(index=True)
    compensation_date = fields.Date(index=True)
    region_text = fields.Char(string='Región operador', index=True)
    region_id = fields.Many2one('commission.region', string='Región análisis', index=True)
    zone_id = fields.Many2one('commission.zone', string='Zona análisis', index=True)
    customer = fields.Char()
    product = fields.Char(index=True)
    concept = fields.Char(index=True)
    service_number = fields.Char(index=True)
    activation_date = fields.Date(index=True)
    regularization_date = fields.Date()
    high_date = fields.Date()
    distributor_type = fields.Char()
    invoice = fields.Char()

    pvp = fields.Monetary()
    reported_percentage_source = fields.Float(
        string='Porcentaje fuente', digits=(16, 6),
        help='Valor numérico tal como viene en Excel. Ejemplo: 0,20 para 20%.',
    )
    reported_percentage = fields.Float(
        string='Porcentaje reportado %', digits=(16, 4),
        help='Porcentaje normalizado en puntos porcentuales. Ejemplo: 20 para 20%.',
    )
    recharges = fields.Monetary()
    consumptions = fields.Monetary()
    base_tariff = fields.Monetary()
    evaluated_consumption = fields.Monetary()
    reported_value = fields.Monetary()
    discounted_base_tariff = fields.Monetary()
    advance_value = fields.Monetary()

    scheme_line_id = fields.Many2one('commission.scheme.line', index=True)
    expected_percentage = fields.Float(digits=(16, 4))
    expected_value = fields.Monetary()
    difference = fields.Monetary(index=True)
    reconciliation_state = fields.Selection(
        [
            ('ok', 'OK'),
            ('no_rule', 'Sin regla'),
            ('difference', 'Diferencia'),
            ('no_purchase', 'ICC sin compra'),
        ],
        default='no_rule', index=True,
    )
    source_file = fields.Char(index=True)
    source_row = fields.Integer()
    currency_id = fields.Many2one(
        'res.currency', default=lambda self: self.env.company.currency_id.id
    )

    _sql_constraints = [
        (
            'source_row_unique',
            'unique(batch_id, source_file, source_row)',
            'La fila fuente ya existe en esta liquidación.',
        )
    ]

    def init(self):
        self.env.cr.execute(
            """
            CREATE INDEX IF NOT EXISTS commission_settlement_line_sim_compensation_idx
                ON commission_settlement_line (sim_id, compensation_date)
            """
        )
        self.env.cr.execute(
            """
            CREATE INDEX IF NOT EXISTS commission_settlement_line_reconciliation_idx
                ON commission_settlement_line (reconciliation_state, batch_id)
            """
        )

    @staticmethod
    def _base_value_from_values(values, rule):
        return {
            'consumption': values.get('evaluated_consumption'),
            'consumptions': values.get('consumptions'),
            'recharges': values.get('recharges'),
            'tariff': values.get('base_tariff'),
        }.get(rule.base_field, 0.0) or 0.0

    @staticmethod
    def _range_matches(base, rule):
        if rule.min_inclusive:
            if base < rule.min_amount:
                return False
        elif base <= rule.min_amount:
            return False

        if rule.no_upper_limit:
            return True
        if not rule.max_amount:
            return True
        if rule.max_inclusive:
            return base <= rule.max_amount
        return base < rule.max_amount

    @staticmethod
    def _text_matches(value, pattern):
        pattern = (pattern or '').strip().casefold()
        if not pattern or pattern == '*':
            return True
        return pattern in (value or '').casefold()

    def _rules_for_operator(self, operator_id):
        return self.env['commission.scheme.line'].search([
            ('scheme_id.operator_id', '=', operator_id),
            ('scheme_id.state', '=', 'active'),
            ('active', '=', True),
        ], order='priority, id')

    def _expected_values_from_dict(self, values, operator_id, rules=None):
        currency = self.env.company.currency_id
        reported = values.get('reported_value') or 0.0
        if not values.get('sim_id'):
            return {
                'scheme_line_id': False,
                'expected_percentage': 0.0,
                'expected_value': 0.0,
                'difference': currency.round(reported),
                'reconciliation_state': 'no_purchase',
            }

        date = values.get('compensation_date') or fields.Date.today()
        concept = values.get('concept') or ''
        product = values.get('product') or ''
        rules = rules if rules is not None else self._rules_for_operator(operator_id)
        chosen = False
        for rule in rules:
            scheme = rule.scheme_id
            if scheme.date_from and date < scheme.date_from:
                continue
            if scheme.date_to and date > scheme.date_to:
                continue
            if not self._text_matches(product, scheme.product_match_pattern):
                continue
            pattern = rule.match_pattern or rule.concept_code or rule.concept_name
            if not self._text_matches(concept, pattern):
                continue
            base = self._base_value_from_values(values, rule)
            if not self._range_matches(base, rule):
                continue
            chosen = rule
            break

        if not chosen:
            return {
                'scheme_line_id': False,
                'expected_percentage': 0.0,
                'expected_value': 0.0,
                'difference': currency.round(reported),
                'reconciliation_state': 'no_rule',
            }

        base = self._base_value_from_values(values, chosen)
        if chosen.calculation_type == 'percentage':
            expected = base * chosen.percentage / 100.0
        else:
            expected = chosen.fixed_amount
        expected = currency.round(expected)
        diff = currency.round(reported - expected)
        return {
            'scheme_line_id': chosen.id,
            'expected_percentage': chosen.percentage if chosen.calculation_type == 'percentage' else 0.0,
            'expected_value': expected,
            'difference': diff,
            'reconciliation_state': 'ok' if currency.is_zero(diff) else 'difference',
        }

    def _recalculate_expected_bulk(self, batch=None):
        """Bulk recalculate using one SQL UPDATE per recordset instead of N ORM writes."""
        records = self
        if batch and not records:
            records = self.search([('batch_id', '=', batch.id)], limit=5000)
        if not records:
            return True

        rules_by_operator = {}
        rows = []
        for rec in records:
            operator_id = rec.batch_id.operator_id.id
            if operator_id not in rules_by_operator:
                rules_by_operator[operator_id] = self._rules_for_operator(operator_id)
            values = {
                'sim_id': rec.sim_id.id,
                'compensation_date': rec.compensation_date,
                'concept': rec.concept,
                'product': rec.product,
                'evaluated_consumption': rec.evaluated_consumption,
                'consumptions': rec.consumptions,
                'recharges': rec.recharges,
                'base_tariff': rec.base_tariff,
                'reported_value': rec.reported_value,
            }
            result = self._expected_values_from_dict(
                values, operator_id, rules=rules_by_operator[operator_id]
            )
            rows.append((
                rec.id,
                result['scheme_line_id'] or None,
                result['expected_percentage'],
                result['expected_value'],
                result['difference'],
                result['reconciliation_state'],
            ))

        execute_values(
            self.env.cr,
            """
            UPDATE commission_settlement_line AS line
               SET scheme_line_id = data.scheme_line_id,
                   expected_percentage = data.expected_percentage,
                   expected_value = data.expected_value,
                   difference = data.difference,
                   reconciliation_state = data.reconciliation_state
              FROM (VALUES %s) AS data(
                   id, scheme_line_id, expected_percentage, expected_value,
                   difference, reconciliation_state)
             WHERE line.id = data.id
            """,
            rows,
            page_size=5000,
        )
        self.invalidate_model([
            'scheme_line_id', 'expected_percentage', 'expected_value',
            'difference', 'reconciliation_state',
        ])
        return True
