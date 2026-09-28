from odoo import fields, models, tools
class CommissionRegionAnalysis(models.Model):
    _name='commission.region.analysis';_description='Rentabilidad por Región y Zona';_auto=False;_order='purchase_month desc, region_id, zone_id'
    purchase_month=fields.Date(readonly=True);region_id=fields.Many2one('commission.region',readonly=True);zone_id=fields.Many2one('commission.zone',readonly=True)
    sim_count=fields.Integer(readonly=True);monetized_count=fields.Integer(readonly=True);purchase_cost=fields.Monetary(readonly=True);reported=fields.Monetary(readonly=True);expected=fields.Monetary(readonly=True);margin=fields.Monetary(readonly=True);difference=fields.Monetary(readonly=True);roi_realized=fields.Float(readonly=True);roi_expected=fields.Float(readonly=True);monetization_rate=fields.Float(readonly=True);currency_id=fields.Many2one('res.currency',readonly=True)
    def init(self):
        tools.drop_view_if_exists(self.env.cr,self._table)
        self.env.cr.execute(f'''CREATE OR REPLACE VIEW {self._table} AS
        WITH comm AS (
          SELECT sim_id, SUM(reported_value) reported, SUM(expected_value) expected
          FROM commission_settlement_line WHERE sim_id IS NOT NULL GROUP BY sim_id
        )
        SELECT row_number() OVER() AS id,
          date_trunc('month',s.purchase_date)::date AS purchase_month,
          s.region_id,s.zone_id,s.currency_id,
          COUNT(s.id)::integer AS sim_count,
          COUNT(s.id) FILTER (WHERE COALESCE(c.reported,0)<>0)::integer AS monetized_count,
          SUM(COALESCE(s.purchase_cost,0)) AS purchase_cost,
          SUM(COALESCE(c.reported,0)) AS reported,
          SUM(COALESCE(c.expected,0)) AS expected,
          SUM(COALESCE(c.reported,0)-COALESCE(s.purchase_cost,0)) AS margin,
          SUM(COALESCE(c.reported,0)-COALESCE(c.expected,0)) AS difference,
          CASE WHEN SUM(COALESCE(s.purchase_cost,0))<>0 THEN (SUM(COALESCE(c.reported,0))-SUM(COALESCE(s.purchase_cost,0)))/SUM(COALESCE(s.purchase_cost,0))*100 ELSE 0 END AS roi_realized,
          CASE WHEN SUM(COALESCE(s.purchase_cost,0))<>0 THEN (SUM(COALESCE(c.expected,0))-SUM(COALESCE(s.purchase_cost,0)))/SUM(COALESCE(s.purchase_cost,0))*100 ELSE 0 END AS roi_expected,
          CASE WHEN COUNT(s.id)<>0 THEN COUNT(s.id) FILTER (WHERE COALESCE(c.reported,0)<>0)::float/COUNT(s.id)*100 ELSE 0 END AS monetization_rate
        FROM commission_sim s LEFT JOIN comm c ON c.sim_id=s.id
        GROUP BY date_trunc('month',s.purchase_date)::date,s.region_id,s.zone_id,s.currency_id''')
