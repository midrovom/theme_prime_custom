from datetime import timedelta

from odoo import api, fields, models


class CommissionDashboard(models.TransientModel):
    _name = 'commission.analysis.dashboard'
    _description = 'Dashboard Análisis de Comisiones'

    operator_id = fields.Many2one('commission.operator', string='Operador')
    date_from = fields.Date(string='Compra desde')
    date_to = fields.Date(string='Compra hasta')
    commission_date_to = fields.Date(
        string='Comisiones hasta',
        help='Fecha de corte para los ingresos y KPI. Vacío = todas las liquidaciones cargadas.',
    )
    region_id = fields.Many2one('commission.region', string='Región')
    zone_id = fields.Many2one(
        'commission.zone', string='Zona', domain="[('region_id', '=', region_id)]"
    )

    # Volumen e inversión
    sim_count = fields.Integer(string='SIM compradas', readonly=True)
    purchase_cost = fields.Monetary(string='Inversión en SIM', readonly=True)
    monetized_count = fields.Integer(string='SIM monetizadas', readonly=True)
    monetization_rate = fields.Float(string='Monetización %', digits=(16, 2), readonly=True)
    mature_count = fields.Integer(
        string='SIM maduras', readonly=True,
        help='SIM cuya compra ya supera el umbral analítico de días configurado en el operador.',
    )
    unproductive_count = fields.Integer(
        string='SIM maduras improductivas', readonly=True,
        help='SIM antiguas según el umbral desde compra y sin comisión neta positiva. No implica por sí sola deuda del operador.',
    )
    unproductive_rate = fields.Float(string='Improductividad maduras %', digits=(16, 2), readonly=True)

    # Ingresos, margen y retorno
    reported = fields.Monetary(string='Comisión recibida', readonly=True)
    expected = fields.Monetary(string='Comisión esperada', readonly=True)
    difference = fields.Monetary(string='Saldo recibido - esperado', readonly=True)
    pending_claro = fields.Monetary(string='Pendiente potencial de Claro', readonly=True)
    commission_line_count = fields.Integer(string='Líneas de comisión', readonly=True)
    ruled_line_count = fields.Integer(string='Líneas con regla', readonly=True)
    rule_coverage_rate = fields.Float(string='Cobertura de reglas %', digits=(16, 2), readonly=True)
    no_rule_reported = fields.Monetary(string='Comisión recibida sin regla', readonly=True)
    difference_line_count = fields.Integer(string='Líneas con diferencia', readonly=True)
    difference_rate = fields.Float(string='Diferencias sobre reglas %', digits=(16, 2), readonly=True)
    margin = fields.Monetary(string='Margen realizado', readonly=True)
    commission_per_sim = fields.Monetary(string='Comisión por SIM', readonly=True)
    margin_per_sim = fields.Monetary(string='Margen neto por SIM', readonly=True)
    roi_realized = fields.Float(string='ROI realizado %', digits=(16, 2), readonly=True)
    roi_expected = fields.Float(string='ROI esperado %', digits=(16, 2), readonly=True)

    # Recuperación de capital
    maturity_days = fields.Integer(string='Madurez usada (días)', readonly=True)
    capital_trapped = fields.Monetary(
        string='Capital maduro sin recuperar', readonly=True,
        help='Saldo de costo aún no recuperado en SIM cuya compra ya superó el umbral analítico. No es una cuenta por cobrar contractual.',
    )
    recovered_count = fields.Integer(string='SIM que recuperaron costo', readonly=True)
    recovery_rate = fields.Float(string='Recuperación %', digits=(16, 2), readonly=True)
    avg_recovery_days = fields.Float(string='Días promedio de recuperación', digits=(16, 1), readonly=True)

    # KPI territorial de lectura inmediata
    top_zone_id = fields.Many2one('commission.zone', string='Zona con mayor comisión', readonly=True)
    top_zone_reported = fields.Monetary(string='Comisión zona líder', readonly=True)
    top_zone_margin = fields.Monetary(string='Margen zona líder', readonly=True)
    top_zone_roi = fields.Float(string='ROI zona líder %', digits=(16, 2), readonly=True)
    top_zone_monetization = fields.Float(string='Monetización zona líder %', digits=(16, 2), readonly=True)
    top_zone_share = fields.Float(string='Participación zona líder %', digits=(16, 2), readonly=True)

    bottom_zone_id = fields.Many2one('commission.zone', string='Zona con menor comisión', readonly=True)
    bottom_zone_reported = fields.Monetary(string='Comisión zona menor', readonly=True)
    bottom_zone_margin = fields.Monetary(string='Margen zona menor', readonly=True)
    bottom_zone_roi = fields.Float(string='ROI zona menor %', digits=(16, 2), readonly=True)
    bottom_zone_monetization = fields.Float(string='Monetización zona menor %', digits=(16, 2), readonly=True)

    best_roi_zone_id = fields.Many2one('commission.zone', string='Zona con mayor ROI', readonly=True)
    best_roi_zone_roi = fields.Float(string='Mejor ROI zonal %', digits=(16, 2), readonly=True)
    best_roi_zone_margin = fields.Monetary(string='Margen zona más eficiente', readonly=True)
    best_roi_zone_monetization = fields.Float(
        string='Monetización zona más eficiente %', digits=(16, 2), readonly=True
    )
    top3_zone_share = fields.Float(
        string='Concentración Top 3 zonas %', digits=(16, 2), readonly=True,
        help='Porcentaje de la comisión recibida que proviene de las tres zonas con mayor generación.',
    )
    zones_analyzed = fields.Integer(string='Zonas analizadas', readonly=True)
    unmapped_zone_count = fields.Integer(string='SIM sin zona', readonly=True)
    zone_coverage_rate = fields.Float(string='Cobertura de zona %', digits=(16, 2), readonly=True)

    currency_id = fields.Many2one(
        'res.currency', default=lambda self: self.env.company.currency_id.id, readonly=True
    )

    def _sim_domain(self):
        self.ensure_one()
        domain = []
        if self.operator_id:
            domain.append(('operator_id', '=', self.operator_id.id))
        if self.date_from:
            domain.append(('purchase_date', '>=', self.date_from))
        if self.date_to:
            domain.append(('purchase_date', '<=', self.date_to))
        if self.region_id:
            domain.append(('region_id', '=', self.region_id.id))
        if self.zone_id:
            domain.append(('zone_id', '=', self.zone_id.id))
        return domain

    def _line_domain(self):
        self.ensure_one()
        domain = [('sim_id', '!=', False)]
        if self.operator_id:
            domain.append(('batch_id.operator_id', '=', self.operator_id.id))
        if self.date_from:
            domain.append(('sim_id.purchase_date', '>=', self.date_from))
        if self.date_to:
            domain.append(('sim_id.purchase_date', '<=', self.date_to))
        if self.region_id:
            domain.append(('sim_id.region_id', '=', self.region_id.id))
        if self.zone_id:
            domain.append(('sim_id.zone_id', '=', self.zone_id.id))
        if self.commission_date_to:
            domain.append(('compensation_date', '<=', self.commission_date_to))
        return domain

    def _sql_sim_filters(self, alias='s'):
        """Return safe SQL filter fragments and params for the selected SIM universe."""
        self.ensure_one()
        clauses = ['1=1']
        params = []
        if self.operator_id:
            clauses.append(f'{alias}.operator_id = %s')
            params.append(self.operator_id.id)
        if self.date_from:
            clauses.append(f'{alias}.purchase_date >= %s')
            params.append(self.date_from)
        if self.date_to:
            clauses.append(f'{alias}.purchase_date <= %s')
            params.append(self.date_to)
        if self.region_id:
            clauses.append(f'{alias}.region_id = %s')
            params.append(self.region_id.id)
        if self.zone_id:
            clauses.append(f'{alias}.zone_id = %s')
            params.append(self.zone_id.id)
        return ' AND '.join(clauses), params

    def _cutoff_sql(self, alias='l'):
        self.ensure_one()
        if self.commission_date_to:
            return f' AND {alias}.compensation_date <= %s', [self.commission_date_to]
        return '', []

    def _maturity_days(self):
        self.ensure_one()
        if self.operator_id:
            return self.operator_id.maturity_days or 90
        return 90

    def _as_of_date(self):
        self.ensure_one()
        return self.commission_date_to or fields.Date.context_today(self)

    def _calculate_metrics(self):
        self.ensure_one()
        where_sql, where_params = self._sql_sim_filters('s')
        cutoff_sql, cutoff_params = self._cutoff_sql('l')
        maturity_days = self._maturity_days()
        mature_date = self._as_of_date() - timedelta(days=maturity_days)

        # One aggregate pass over the selected SIM universe. Pending Claro is deliberately
        # summed by line so an overpayment on one concept does not hide a shortage on another.
        query = f"""
            WITH selected_sims AS (
                SELECT s.id, s.purchase_cost, s.purchase_date, s.zone_id, s.region_id,
                       s.operator_id, s.currency_id
                  FROM commission_sim s
                 WHERE {where_sql}
            ),
            comm AS (
                SELECT l.sim_id,
                       COALESCE(SUM(l.reported_value), 0) AS reported,
                       COALESCE(SUM(l.expected_value), 0) AS expected,
                       COALESCE(SUM(GREATEST(COALESCE(l.expected_value, 0)
                                             - COALESCE(l.reported_value, 0), 0)), 0) AS pending,
                       COUNT(*)::integer AS line_count,
                       COUNT(*) FILTER (WHERE l.scheme_line_id IS NOT NULL)::integer AS ruled_count,
                       COUNT(*) FILTER (WHERE l.reconciliation_state = 'difference')::integer
                           AS difference_count,
                       COALESCE(SUM(
                           CASE WHEN l.reconciliation_state = 'no_rule'
                                THEN COALESCE(l.reported_value, 0) ELSE 0 END
                       ), 0) AS no_rule_reported
                  FROM commission_settlement_line l
                  JOIN selected_sims ss ON ss.id = l.sim_id
                 WHERE 1=1 {cutoff_sql}
                 GROUP BY l.sim_id
            ),
            per_sim AS (
                SELECT ss.*,
                       COALESCE(c.reported, 0) AS reported,
                       COALESCE(c.expected, 0) AS expected,
                       COALESCE(c.pending, 0) AS pending,
                       COALESCE(c.line_count, 0) AS line_count,
                       COALESCE(c.ruled_count, 0) AS ruled_count,
                       COALESCE(c.difference_count, 0) AS difference_count,
                       COALESCE(c.no_rule_reported, 0) AS no_rule_reported
                  FROM selected_sims ss
                  LEFT JOIN comm c ON c.sim_id = ss.id
            )
            SELECT COUNT(*)::integer AS sim_count,
                   COALESCE(SUM(purchase_cost), 0) AS purchase_cost,
                   COUNT(*) FILTER (WHERE reported > 0)::integer AS monetized_count,
                   COUNT(*) FILTER (WHERE zone_id IS NULL)::integer AS unmapped_zone_count,
                   COALESCE(SUM(reported), 0) AS reported,
                   COALESCE(SUM(expected), 0) AS expected,
                   COALESCE(SUM(pending), 0) AS pending_claro,
                   COALESCE(SUM(line_count), 0)::integer AS commission_line_count,
                   COALESCE(SUM(ruled_count), 0)::integer AS ruled_line_count,
                   COALESCE(SUM(difference_count), 0)::integer AS difference_line_count,
                   COALESCE(SUM(no_rule_reported), 0) AS no_rule_reported,
                   COUNT(*) FILTER (WHERE purchase_date IS NOT NULL AND purchase_date <= %s)::integer
                       AS mature_count,
                   COUNT(*) FILTER (
                       WHERE purchase_date IS NOT NULL AND purchase_date <= %s AND reported <= 0
                   )::integer AS unproductive_count,
                   COALESCE(SUM(
                       CASE WHEN purchase_date IS NOT NULL AND purchase_date <= %s
                                  AND COALESCE(purchase_cost, 0) > reported
                            THEN COALESCE(purchase_cost, 0) - reported
                            ELSE 0 END
                   ), 0) AS capital_trapped,
                   COUNT(*) FILTER (
                       WHERE COALESCE(purchase_cost, 0) > 0 AND reported >= purchase_cost
                   )::integer AS recovered_count
              FROM per_sim
        """
        params = where_params + cutoff_params + [mature_date, mature_date, mature_date]
        self.env.cr.execute(query, params)
        row = self.env.cr.dictfetchone() or {}

        sim_count = row.get('sim_count') or 0
        purchase_cost = row.get('purchase_cost') or 0.0
        monetized_count = row.get('monetized_count') or 0
        unmapped_zone_count = row.get('unmapped_zone_count') or 0
        reported = row.get('reported') or 0.0
        expected = row.get('expected') or 0.0
        pending_claro = row.get('pending_claro') or 0.0
        commission_line_count = row.get('commission_line_count') or 0
        ruled_line_count = row.get('ruled_line_count') or 0
        difference_line_count = row.get('difference_line_count') or 0
        no_rule_reported = row.get('no_rule_reported') or 0.0
        mature_count = row.get('mature_count') or 0
        unproductive_count = row.get('unproductive_count') or 0
        capital_trapped = row.get('capital_trapped') or 0.0
        recovered_count = row.get('recovered_count') or 0
        margin = reported - purchase_cost

        values = {
            'sim_count': sim_count,
            'monetized_count': monetized_count,
            'monetization_rate': (monetized_count / sim_count * 100.0) if sim_count else 0.0,
            'unmapped_zone_count': unmapped_zone_count,
            'zone_coverage_rate': (
                (sim_count - unmapped_zone_count) / sim_count * 100.0 if sim_count else 0.0
            ),
            'purchase_cost': purchase_cost,
            'mature_count': mature_count,
            'unproductive_count': unproductive_count,
            'unproductive_rate': (
                unproductive_count / mature_count * 100.0 if mature_count else 0.0
            ),
            'reported': reported,
            'expected': expected,
            'difference': reported - expected,
            'pending_claro': pending_claro,
            'commission_line_count': commission_line_count,
            'ruled_line_count': ruled_line_count,
            'rule_coverage_rate': (
                ruled_line_count / commission_line_count * 100.0 if commission_line_count else 0.0
            ),
            'no_rule_reported': no_rule_reported,
            'difference_line_count': difference_line_count,
            'difference_rate': (
                difference_line_count / ruled_line_count * 100.0 if ruled_line_count else 0.0
            ),
            'margin': margin,
            'commission_per_sim': (reported / sim_count) if sim_count else 0.0,
            'margin_per_sim': (margin / sim_count) if sim_count else 0.0,
            'roi_realized': (margin / purchase_cost * 100.0) if purchase_cost else 0.0,
            'roi_expected': (
                (expected - purchase_cost) / purchase_cost * 100.0 if purchase_cost else 0.0
            ),
            'maturity_days': maturity_days,
            'capital_trapped': capital_trapped,
            'recovered_count': recovered_count,
            'recovery_rate': (recovered_count / sim_count * 100.0) if sim_count else 0.0,
            'avg_recovery_days': self._average_recovery_days(
                where_sql, where_params, cutoff_sql, cutoff_params
            ),
        }
        values.update(
            self._zone_metrics(where_sql, where_params, cutoff_sql, cutoff_params, reported)
        )
        return values

    def _average_recovery_days(self, where_sql, where_params, cutoff_sql, cutoff_params):
        """Average days until cumulative received commissions recover the SIM purchase cost."""
        query = f"""
            WITH selected_sims AS (
                SELECT s.id, s.purchase_cost, s.purchase_date
                  FROM commission_sim s
                 WHERE {where_sql}
                   AND s.purchase_date IS NOT NULL
                   AND COALESCE(s.purchase_cost, 0) > 0
            ),
            ordered AS (
                SELECT l.sim_id, l.compensation_date, l.id,
                       SUM(COALESCE(l.reported_value, 0)) OVER (
                           PARTITION BY l.sim_id
                           ORDER BY l.compensation_date, l.id
                           ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
                       ) AS cumulative_reported
                  FROM commission_settlement_line l
                  JOIN selected_sims ss ON ss.id = l.sim_id
                 WHERE l.compensation_date IS NOT NULL
                   AND l.compensation_date >= ss.purchase_date
                   {cutoff_sql}
            ),
            recovered AS (
                SELECT o.sim_id, MIN(o.compensation_date) AS recovery_date
                  FROM ordered o
                  JOIN selected_sims ss ON ss.id = o.sim_id
                 WHERE o.cumulative_reported >= ss.purchase_cost
                 GROUP BY o.sim_id
            )
            SELECT COALESCE(AVG((r.recovery_date - ss.purchase_date)::numeric), 0) AS avg_days
              FROM recovered r
              JOIN selected_sims ss ON ss.id = r.sim_id
        """
        self.env.cr.execute(query, where_params + cutoff_params)
        row = self.env.cr.dictfetchone() or {}
        return float(row.get('avg_days') or 0.0)

    def _zone_metrics(self, where_sql, where_params, cutoff_sql, cutoff_params, total_reported):
        """Return highest/lowest generating zones and the highest ROI zone."""
        query = f"""
            WITH selected_sims AS (
                SELECT s.id, s.purchase_cost, s.zone_id
                  FROM commission_sim s
                 WHERE {where_sql}
                   AND s.zone_id IS NOT NULL
            ),
            comm AS (
                SELECT l.sim_id,
                       COALESCE(SUM(l.reported_value), 0) AS reported,
                       COALESCE(SUM(l.expected_value), 0) AS expected
                  FROM commission_settlement_line l
                  JOIN selected_sims ss ON ss.id = l.sim_id
                 WHERE 1=1 {cutoff_sql}
                 GROUP BY l.sim_id
            ),
            zone_data AS (
                SELECT ss.zone_id,
                       COUNT(*)::integer AS sim_count,
                       COUNT(*) FILTER (WHERE COALESCE(c.reported, 0) > 0)::integer AS monetized_count,
                       COALESCE(SUM(ss.purchase_cost), 0) AS purchase_cost,
                       COALESCE(SUM(c.reported), 0) AS reported,
                       COALESCE(SUM(c.expected), 0) AS expected
                  FROM selected_sims ss
                  LEFT JOIN comm c ON c.sim_id = ss.id
                 GROUP BY ss.zone_id
            )
            SELECT zone_id, sim_count, monetized_count, purchase_cost, reported, expected,
                   reported - purchase_cost AS margin,
                   CASE WHEN purchase_cost <> 0
                        THEN (reported - purchase_cost) / purchase_cost * 100
                        ELSE 0 END AS roi,
                   CASE WHEN sim_count <> 0
                        THEN monetized_count::float / sim_count * 100
                        ELSE 0 END AS monetization
              FROM zone_data
        """
        self.env.cr.execute(query, where_params + cutoff_params)
        rows = self.env.cr.dictfetchall()

        empty = {
            'top_zone_id': False,
            'top_zone_reported': 0.0,
            'top_zone_margin': 0.0,
            'top_zone_roi': 0.0,
            'top_zone_monetization': 0.0,
            'top_zone_share': 0.0,
            'bottom_zone_id': False,
            'bottom_zone_reported': 0.0,
            'bottom_zone_margin': 0.0,
            'bottom_zone_roi': 0.0,
            'bottom_zone_monetization': 0.0,
            'best_roi_zone_id': False,
            'best_roi_zone_roi': 0.0,
            'best_roi_zone_margin': 0.0,
            'best_roi_zone_monetization': 0.0,
            'top3_zone_share': 0.0,
            'zones_analyzed': len(rows),
        }
        if not rows:
            return empty

        top = max(rows, key=lambda r: ((r.get('reported') or 0.0), (r.get('margin') or 0.0)))
        # For equal low revenue, surface the zone with more SIM because it represents a bigger concern.
        bottom = min(rows, key=lambda r: ((r.get('reported') or 0.0), -(r.get('sim_count') or 0)))
        roi_candidates = [r for r in rows if (r.get('purchase_cost') or 0.0) > 0] or rows
        best_roi = max(
            roi_candidates,
            key=lambda r: ((r.get('roi') or 0.0), (r.get('reported') or 0.0)),
        )
        top3_reported = sum(
            (r.get('reported') or 0.0)
            for r in sorted(rows, key=lambda r: r.get('reported') or 0.0, reverse=True)[:3]
        )

        empty.update({
            'top_zone_id': top['zone_id'],
            'top_zone_reported': top.get('reported') or 0.0,
            'top_zone_margin': top.get('margin') or 0.0,
            'top_zone_roi': top.get('roi') or 0.0,
            'top_zone_monetization': top.get('monetization') or 0.0,
            'top_zone_share': (
                (top.get('reported') or 0.0) / total_reported * 100.0 if total_reported else 0.0
            ),
            'bottom_zone_id': bottom['zone_id'],
            'bottom_zone_reported': bottom.get('reported') or 0.0,
            'bottom_zone_margin': bottom.get('margin') or 0.0,
            'bottom_zone_roi': bottom.get('roi') or 0.0,
            'bottom_zone_monetization': bottom.get('monetization') or 0.0,
            'best_roi_zone_id': best_roi['zone_id'],
            'best_roi_zone_roi': best_roi.get('roi') or 0.0,
            'best_roi_zone_margin': best_roi.get('margin') or 0.0,
            'best_roi_zone_monetization': best_roi.get('monetization') or 0.0,
            'top3_zone_share': (top3_reported / total_reported * 100.0) if total_reported else 0.0,
        })
        return empty

    @api.onchange(
        'operator_id', 'date_from', 'date_to', 'commission_date_to', 'region_id', 'zone_id'
    )
    def _onchange_filters(self):
        for record in self:
            if record.date_from and record.date_to and record.date_from > record.date_to:
                continue
            values = record._calculate_metrics()
            for key, value in values.items():
                record[key] = value

    def action_refresh(self):
        """Public RPC method used by the form button."""
        self.ensure_one()
        values = self._calculate_metrics()
        self.write(values)
        return {
            'type': 'ir.actions.act_window',
            'name': 'Dashboard de Comisiones',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_open_region_analysis(self):
        self.ensure_one()
        domain = []
        if self.operator_id:
            domain.append(('operator_id', '=', self.operator_id.id))
        if self.region_id:
            domain.append(('region_id', '=', self.region_id.id))
        if self.zone_id:
            domain.append(('zone_id', '=', self.zone_id.id))
        if self.date_from:
            domain.append(('purchase_month', '>=', self.date_from.replace(day=1)))
        if self.date_to:
            domain.append(('purchase_month', '<=', self.date_to))
        return {
            'type': 'ir.actions.act_window',
            'name': 'Rendimiento por Región / Zona',
            'res_model': 'commission.region.analysis',
            'view_mode': 'list,pivot,graph',
            'domain': domain,
            'target': 'current',
        }

    def action_open_pending_claro(self):
        self.ensure_one()
        domain = self._line_domain() + [('difference', '<', 0)]
        return {
            'type': 'ir.actions.act_window',
            'name': 'Pendiente potencial de Claro',
            'res_model': 'commission.settlement.line',
            'view_mode': 'list,pivot,graph',
            'domain': domain,
            'target': 'current',
        }
