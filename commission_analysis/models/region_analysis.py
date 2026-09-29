from odoo import fields, models, tools


class CommissionRegionAnalysis(models.Model):
    _name = 'commission.region.analysis'
    _description = 'Rentabilidad por Región y Zona'
    _auto = False
    _order = 'purchase_month desc, reported desc, region_id, zone_id'

    purchase_month = fields.Date(readonly=True)
    operator_id = fields.Many2one('commission.operator', readonly=True)
    region_id = fields.Many2one('commission.region', readonly=True)
    zone_id = fields.Many2one('commission.zone', readonly=True)
    sim_count = fields.Integer(readonly=True)
    monetized_count = fields.Integer(readonly=True)
    mature_count = fields.Integer(readonly=True)
    unproductive_count = fields.Integer(readonly=True)
    purchase_cost = fields.Monetary(readonly=True)
    reported = fields.Monetary(string='Comisión recibida', readonly=True)
    expected = fields.Monetary(string='Comisión esperada', readonly=True)
    margin = fields.Monetary(readonly=True)
    difference = fields.Monetary(readonly=True)
    commission_per_sim = fields.Monetary(string='Comisión por SIM', readonly=True)
    margin_per_sim = fields.Monetary(string='Margen por SIM', readonly=True)
    capital_trapped = fields.Monetary(string='Capital maduro sin recuperar', readonly=True)
    roi_realized = fields.Float(string='ROI realizado %', readonly=True)
    roi_expected = fields.Float(string='ROI esperado %', readonly=True)
    monetization_rate = fields.Float(string='Monetización %', readonly=True)
    unproductive_rate = fields.Float(string='Improductividad maduras %', readonly=True)
    participation = fields.Float(string='Participación cohorte %', readonly=True)
    currency_id = fields.Many2one('res.currency', readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute(f"""
            CREATE OR REPLACE VIEW {self._table} AS
            WITH comm AS (
                SELECT sim_id,
                       SUM(reported_value) AS reported,
                       SUM(expected_value) AS expected
                  FROM commission_settlement_line
                 WHERE sim_id IS NOT NULL
                 GROUP BY sim_id
            ),
            grouped AS (
                SELECT date_trunc('month', s.purchase_date)::date AS purchase_month,
                       s.operator_id,
                       s.region_id,
                       s.zone_id,
                       s.currency_id,
                       COUNT(s.id)::integer AS sim_count,
                       COUNT(s.id) FILTER (WHERE COALESCE(c.reported, 0) > 0)::integer
                           AS monetized_count,
                       COUNT(s.id) FILTER (
                           WHERE s.purchase_date IS NOT NULL
                             AND s.purchase_date <= CURRENT_DATE
                                 - (COALESCE(o.maturity_days, 90) * INTERVAL '1 day')
                       )::integer AS mature_count,
                       COUNT(s.id) FILTER (
                           WHERE s.purchase_date IS NOT NULL
                             AND s.purchase_date <= CURRENT_DATE
                                 - (COALESCE(o.maturity_days, 90) * INTERVAL '1 day')
                             AND COALESCE(c.reported, 0) <= 0
                       )::integer AS unproductive_count,
                       SUM(COALESCE(s.purchase_cost, 0)) AS purchase_cost,
                       SUM(COALESCE(c.reported, 0)) AS reported,
                       SUM(COALESCE(c.expected, 0)) AS expected,
                       SUM(COALESCE(c.reported, 0) - COALESCE(s.purchase_cost, 0)) AS margin,
                       SUM(COALESCE(c.reported, 0) - COALESCE(c.expected, 0)) AS difference,
                       SUM(
                           CASE
                               WHEN s.purchase_date IS NOT NULL
                                AND s.purchase_date <= CURRENT_DATE
                                    - (COALESCE(o.maturity_days, 90) * INTERVAL '1 day')
                                AND COALESCE(s.purchase_cost, 0) > COALESCE(c.reported, 0)
                               THEN COALESCE(s.purchase_cost, 0) - COALESCE(c.reported, 0)
                               ELSE 0
                           END
                       ) AS capital_trapped
                  FROM commission_sim s
                  JOIN commission_operator o ON o.id = s.operator_id
                  LEFT JOIN comm c ON c.sim_id = s.id
                 GROUP BY date_trunc('month', s.purchase_date)::date,
                          s.operator_id, s.region_id, s.zone_id, s.currency_id
            )
            SELECT row_number() OVER (
                       ORDER BY g.purchase_month DESC, g.operator_id,
                                g.reported DESC, g.region_id, g.zone_id
                   ) AS id,
                   g.purchase_month,
                   g.operator_id,
                   g.region_id,
                   g.zone_id,
                   g.currency_id,
                   g.sim_count,
                   g.monetized_count,
                   g.mature_count,
                   g.unproductive_count,
                   g.purchase_cost,
                   g.reported,
                   g.expected,
                   g.margin,
                   g.difference,
                   g.capital_trapped,
                   CASE WHEN g.sim_count <> 0
                        THEN g.reported / g.sim_count
                        ELSE 0 END AS commission_per_sim,
                   CASE WHEN g.sim_count <> 0
                        THEN g.margin / g.sim_count
                        ELSE 0 END AS margin_per_sim,
                   CASE WHEN g.purchase_cost <> 0
                        THEN g.margin / g.purchase_cost * 100
                        ELSE 0 END AS roi_realized,
                   CASE WHEN g.purchase_cost <> 0
                        THEN (g.expected - g.purchase_cost) / g.purchase_cost * 100
                        ELSE 0 END AS roi_expected,
                   CASE WHEN g.sim_count <> 0
                        THEN g.monetized_count::float / g.sim_count * 100
                        ELSE 0 END AS monetization_rate,
                   CASE WHEN g.mature_count <> 0
                        THEN g.unproductive_count::float / g.mature_count * 100
                        ELSE 0 END AS unproductive_rate,
                   CASE WHEN SUM(g.reported) OVER (
                                      PARTITION BY g.operator_id, g.purchase_month
                                  ) <> 0
                        THEN g.reported / SUM(g.reported) OVER (
                                      PARTITION BY g.operator_id, g.purchase_month
                                  ) * 100
                        ELSE 0 END AS participation
              FROM grouped g
        """)
