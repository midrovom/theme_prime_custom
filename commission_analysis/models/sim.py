from odoo import fields, models


class CommissionSim(models.Model):
    _name = 'commission.sim'
    _description = 'SIM / ICC'
    _inherit = ['mail.thread']
    _rec_name = 'icc'
    _order = 'purchase_date desc, id desc'

    icc = fields.Char(required=True, index=True, tracking=True)
    icc_key = fields.Char(
        required=True,
        index=True,
        help='Clave normalizada para cruces entre archivos según la longitud configurada en el operador.',
    )
    operator_id = fields.Many2one('commission.operator', required=True, index=True)
    product = fields.Char(index=True)
    purchase_date = fields.Date(index=True)
    invoice = fields.Char(index=True)
    warehouse = fields.Char(index=True)
    region_id = fields.Many2one('commission.region', index=True)
    zone_id = fields.Many2one('commission.zone', index=True)
    purchase_cost = fields.Monetary(
        string='Costo para ROI',
        help='Inversión por SIM según la base de costo configurada en el operador.',
    )
    currency_id = fields.Many2one(
        'res.currency', default=lambda self: self.env.company.currency_id.id
    )
    purchase_line_ids = fields.One2many('commission.purchase.line', 'sim_id')
    commission_line_ids = fields.One2many('commission.settlement.line', 'sim_id')

    # Stored analytical KPIs. They are refreshed in bulk after imports/recalculations.
    realized_commission = fields.Monetary(readonly=True, default=0)
    expected_commission = fields.Monetary(readonly=True, default=0)
    margin_realized = fields.Monetary(readonly=True, default=0)
    roi_realized = fields.Float(readonly=True, digits=(16, 2), default=0)
    roi_expected = fields.Float(readonly=True, digits=(16, 2), default=0)
    monetized = fields.Boolean(readonly=True, default=False, index=True)

    def init(self):
        self.env.cr.execute(
            """
            CREATE INDEX IF NOT EXISTS commission_sim_analysis_idx
                ON commission_sim (operator_id, purchase_date, region_id, zone_id)
            """
        )

    _sql_constraints = [
        (
            'operator_icc_uniq',
            'unique(operator_id, icc)',
            'El ICC/SIMCARD ya existe para este operador.',
        ),
        (
            'operator_icc_key_uniq',
            'unique(operator_id, icc_key)',
            'La clave normalizada del ICC ya existe para este operador.',
        ),
    ]

    def _refresh_kpis(self, sim_ids=None):
        """Refresh stored ROI/commission KPIs with one aggregate SQL statement."""
        ids = list(set(sim_ids or self.ids))
        if not ids:
            return True
        self.flush_model(['purchase_cost'])
        self.env['commission.settlement.line'].flush_model([
            'sim_id', 'reported_value', 'expected_value',
        ])
        self.env.cr.execute(
            """
            WITH agg AS (
                SELECT sim_id,
                       COALESCE(SUM(reported_value), 0) AS reported,
                       COALESCE(SUM(expected_value), 0) AS expected
                  FROM commission_settlement_line
                 WHERE sim_id = ANY(%s)
                 GROUP BY sim_id
            )
            UPDATE commission_sim s
               SET realized_commission = COALESCE(a.reported, 0),
                   expected_commission = COALESCE(a.expected, 0),
                   margin_realized = COALESCE(a.reported, 0) - COALESCE(s.purchase_cost, 0),
                   roi_realized = CASE
                       WHEN COALESCE(s.purchase_cost, 0) <> 0
                       THEN ((COALESCE(a.reported, 0) - s.purchase_cost) / s.purchase_cost) * 100
                       ELSE 0 END,
                   roi_expected = CASE
                       WHEN COALESCE(s.purchase_cost, 0) <> 0
                       THEN ((COALESCE(a.expected, 0) - s.purchase_cost) / s.purchase_cost) * 100
                       ELSE 0 END,
                   monetized = COALESCE(a.reported, 0) > 0
              FROM (SELECT id FROM commission_sim WHERE id = ANY(%s)) target
              LEFT JOIN agg a ON a.sim_id = target.id
             WHERE s.id = target.id
            """,
            (ids, ids),
        )
        self.invalidate_model([
            'realized_commission', 'expected_commission', 'margin_realized',
            'roi_realized', 'roi_expected', 'monetized',
        ])
        return True
