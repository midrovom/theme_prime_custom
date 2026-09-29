from psycopg2.extras import execute_values

from odoo import api, fields, models, _
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
    matched_line_count = fields.Integer(compute='_compute_totals', string='ICC vinculados')
    no_purchase_count = fields.Integer(compute='_compute_totals', string='ICC sin compra')
    ruled_line_count = fields.Integer(compute='_compute_totals', string='Con regla')
    no_rule_count = fields.Integer(compute='_compute_totals', string='Sin regla')
    difference_count = fields.Integer(compute='_compute_totals', string='Con diferencia')
    ok_count = fields.Integer(compute='_compute_totals', string='OK')
    data_error_count = fields.Integer(compute='_compute_totals', string='Datos incompletos')
    rule_coverage_rate = fields.Float(compute='_compute_totals', string='Cobertura de reglas %', digits=(16, 2))
    reported_total = fields.Monetary(compute='_compute_totals', string='Reportado')
    expected_total = fields.Monetary(compute='_compute_totals', string='Esperado')
    difference_total = fields.Monetary(compute='_compute_totals', string='Diferencia')
    currency_id = fields.Many2one(
        'res.currency', default=lambda self: self.env.company.currency_id.id
    )

    def _compute_totals(self):
        # Asegura que los CREATE/WRITE pendientes sean visibles para los agregados SQL.
        self.env['commission.settlement.line'].flush_model([
            'batch_id', 'sim_id', 'scheme_line_id', 'reconciliation_state',
            'reported_value', 'expected_value', 'difference',
        ])
        for rec in self:
            if not rec.id:
                rec.line_count = rec.matched_line_count = rec.no_purchase_count = 0
                rec.ruled_line_count = rec.no_rule_count = rec.difference_count = 0
                rec.ok_count = rec.data_error_count = 0
                rec.rule_coverage_rate = 0.0
                rec.reported_total = rec.expected_total = rec.difference_total = 0.0
                continue
            self.env.cr.execute(
                """
                SELECT COUNT(*)::integer AS line_count,
                       COUNT(*) FILTER (WHERE sim_id IS NOT NULL)::integer AS matched_line_count,
                       COUNT(*) FILTER (WHERE reconciliation_state = 'no_purchase')::integer AS no_purchase_count,
                       COUNT(*) FILTER (WHERE scheme_line_id IS NOT NULL)::integer AS ruled_line_count,
                       COUNT(*) FILTER (WHERE reconciliation_state = 'no_rule')::integer AS no_rule_count,
                       COUNT(*) FILTER (WHERE reconciliation_state = 'difference')::integer AS difference_count,
                       COUNT(*) FILTER (WHERE reconciliation_state = 'ok')::integer AS ok_count,
                       COUNT(*) FILTER (WHERE reconciliation_state = 'data_error')::integer AS data_error_count,
                       COALESCE(SUM(reported_value), 0) AS reported_total,
                       COALESCE(SUM(expected_value), 0) AS expected_total,
                       COALESCE(SUM(difference), 0) AS difference_total
                  FROM commission_settlement_line
                 WHERE batch_id = %s
                """,
                (rec.id,),
            )
            values = self.env.cr.dictfetchone() or {}
            rec.line_count = values.get('line_count') or 0
            rec.matched_line_count = values.get('matched_line_count') or 0
            rec.no_purchase_count = values.get('no_purchase_count') or 0
            rec.ruled_line_count = values.get('ruled_line_count') or 0
            rec.no_rule_count = values.get('no_rule_count') or 0
            rec.difference_count = values.get('difference_count') or 0
            rec.ok_count = values.get('ok_count') or 0
            rec.data_error_count = values.get('data_error_count') or 0
            rec.rule_coverage_rate = (
                rec.ruled_line_count / rec.matched_line_count * 100.0
                if rec.matched_line_count else 0.0
            )
            rec.reported_total = values.get('reported_total') or 0.0
            rec.expected_total = values.get('expected_total') or 0.0
            rec.difference_total = values.get('difference_total') or 0.0

    def write(self, vals):
        if 'operator_id' in vals:
            Line = self.env['commission.settlement.line']
            ImportFile = self.env['commission.import.file']
            for rec in self:
                if rec.operator_id.id != vals.get('operator_id'):
                    has_data = (
                        bool(Line.search([('batch_id', '=', rec.id)], limit=1))
                        or bool(ImportFile.search([('settlement_batch_id', '=', rec.id)], limit=1))
                    )
                    if has_data:
                        raise UserError(_(
                            'No se puede cambiar el operador de una liquidación que ya contiene archivos o registros.'
                        ))
        return super().write(vals)

    def action_recalculate(self):
        """Re-vincula ICC, sincroniza geografía, recalcula reglas y refresca KPI.

        El orden de carga deja de importar: si las comisiones fueron cargadas antes que las
        compras, este proceso vuelve a relacionar las líneas por ICC normalizado antes de
        aplicar las reglas.
        """
        Line = self.env['commission.settlement.line']
        Sim = self.env['commission.sim']
        for batch in self:
            if batch.state == 'closed':
                raise UserError(_('No se puede recalcular una liquidación cerrada.'))

            # 1) Re-vincular por operador + clave ICC y sincronizar Región/Zona desde el maestro SIM.
            Line._match_sims_bulk(operator_id=batch.operator_id.id, batch_id=batch.id)

            # 2) Recalcular cada línea con las reglas vigentes. Si ninguna versión puede
            # aplicar al rango de fechas del lote, usar un UPDATE SQL único: es el caso
            # normal de un período histórico aún no parametrizado y evita recorrer 240k filas.
            self.env.cr.execute(
                "SELECT MIN(compensation_date), MAX(compensation_date) "
                "FROM commission_settlement_line WHERE batch_id=%s",
                (batch.id,),
            )
            min_date, max_date = self.env.cr.fetchone() or (None, None)
            operator_rules = Line._rules_for_operator(batch.operator_id.id)
            applicable_rules = operator_rules.filtered(
                lambda r: min_date and max_date
                and (not r.scheme_id.date_from or r.scheme_id.date_from <= max_date)
                and (not r.scheme_id.date_to or r.scheme_id.date_to >= min_date)
            )

            affected_sim_ids = set()
            if not applicable_rules:
                Line._recalculate_no_rules_bulk(batch.id)
                self.env.cr.execute(
                    "SELECT DISTINCT sim_id FROM commission_settlement_line "
                    "WHERE batch_id=%s AND sim_id IS NOT NULL",
                    (batch.id,),
                )
                affected_sim_ids.update(row[0] for row in self.env.cr.fetchall())
            else:
                last_id = 0
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

            # 3) Actualizar KPI acumulados de las SIM afectadas.
            sim_ids = list(affected_sim_ids)
            for start in range(0, len(sim_ids), 10000):
                Sim._refresh_kpis(sim_ids[start:start + 10000])
            if batch.state == 'draft':
                batch.state = 'processed'
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
            ('data_error', 'Dato incompleto'),
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
        self.env.cr.execute(
            """
            CREATE INDEX IF NOT EXISTS commission_settlement_line_operator_icc_idx
                ON commission_settlement_line (operator_id, icc_key)
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
            ('scheme_id.state', 'in', ('active', 'closed')),
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

        date = values.get('compensation_date')
        if not date:
            return {
                'scheme_line_id': False,
                'expected_percentage': 0.0,
                'expected_value': 0.0,
                'difference': currency.round(reported),
                'reconciliation_state': 'data_error',
            }
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

    @api.model
    def _match_sims_bulk(self, operator_id, batch_id=None, sim_ids=None):
        """Vincula líneas a SIM por ICC normalizado y sincroniza Región/Zona.

        Se usa tanto en recalculación como después de importar compras, de modo que el
        resultado sea independiente del orden de carga. Devuelve los IDs de líneas y SIM
        cuyo vínculo o geografía fue actualizado.
        """
        # Raw SQL debe operar sobre valores ya persistidos, incluidos campos related/store.
        self.flush_model(['operator_id', 'icc_key', 'batch_id', 'sim_id', 'region_id', 'zone_id'])
        self.env['commission.sim'].flush_model(['operator_id', 'icc_key', 'region_id', 'zone_id'])
        clauses = ['l.operator_id = %s', 's.operator_id = %s', 'l.icc_key = s.icc_key']
        params = [operator_id, operator_id]
        if batch_id:
            clauses.append('l.batch_id = %s')
            params.append(batch_id)
        if sim_ids is not None:
            sim_ids = list(set(sim_ids))
            if not sim_ids:
                return [], []
            clauses.append('s.id = ANY(%s)')
            params.append(sim_ids)
        where_sql = ' AND '.join(clauses)
        self.env.cr.execute(
            f"""
            UPDATE commission_settlement_line l
               SET sim_id = s.id,
                   region_id = COALESCE(s.region_id, l.region_id),
                   zone_id = s.zone_id
              FROM commission_sim s
             WHERE {where_sql}
               AND (l.sim_id IS DISTINCT FROM s.id
                    OR l.region_id IS DISTINCT FROM COALESCE(s.region_id, l.region_id)
                    OR l.zone_id IS DISTINCT FROM s.zone_id)
            RETURNING l.id, s.id
            """,
            params,
        )
        changed = self.env.cr.fetchall()
        if changed:
            self.invalidate_model(['sim_id', 'region_id', 'zone_id'])
        return [row[0] for row in changed], [row[1] for row in changed]

    @api.model
    def _recalculate_no_rules_bulk(self, batch_id):
        """Fast path when no scheme can apply to the settlement date range."""
        self.flush_model([
            'batch_id', 'sim_id', 'compensation_date', 'reported_value',
            'scheme_line_id', 'expected_percentage', 'expected_value',
            'difference', 'reconciliation_state',
        ])
        decimals = self.env.company.currency_id.decimal_places or 2
        self.env.cr.execute(
            """
            UPDATE commission_settlement_line
               SET scheme_line_id = NULL,
                   expected_percentage = 0,
                   expected_value = 0,
                   difference = ROUND(COALESCE(reported_value, 0)::numeric, %s)::double precision,
                   reconciliation_state = CASE
                       WHEN sim_id IS NULL THEN 'no_purchase'
                       WHEN compensation_date IS NULL THEN 'data_error'
                       ELSE 'no_rule'
                   END
             WHERE batch_id = %s
            """,
            (decimals, batch_id),
        )
        self.invalidate_model([
            'scheme_line_id', 'expected_percentage', 'expected_value',
            'difference', 'reconciliation_state',
        ])
        return True

    def _recalculate_expected_bulk(self, batch=None):
        """Bulk recalculate using one SQL UPDATE per recordset instead of N ORM writes."""
        records = self
        if batch and not records:
            records = self.search([('batch_id', '=', batch.id)], limit=5000)
        if not records:
            return True

        # Fuerza la persistencia de campos que serán leídos/calculados antes del UPDATE SQL.
        records.flush_recordset([
            'batch_id', 'sim_id', 'compensation_date', 'concept', 'product',
            'evaluated_consumption', 'consumptions', 'recharges', 'base_tariff',
            'reported_value',
        ])
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

        # IMPORTANT: explicit casts are required. When every scheme_line_id in a batch is
        # NULL (a normal case when no historical scheme is configured), PostgreSQL infers the
        # VALUES column as text unless it is typed explicitly, causing a DatatypeMismatch on
        # the integer Many2one column.
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
            template=(
                '(%s::integer, %s::integer, %s::double precision, '
                '%s::double precision, %s::double precision, %s::varchar)'
            ),
            page_size=5000,
        )
        self.invalidate_model([
            'scheme_line_id', 'expected_percentage', 'expected_value',
            'difference', 'reconciliation_state',
        ])
        return True
