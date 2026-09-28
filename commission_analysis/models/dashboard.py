from odoo import api, fields, models
class CommissionDashboard(models.TransientModel):
    _name='commission.analysis.dashboard';_description='Dashboard Análisis de Comisiones'
    date_from=fields.Date(string='Compra desde');date_to=fields.Date(string='Compra hasta');commission_date_to=fields.Date(string='Comisiones hasta');region_id=fields.Many2one('commission.region');zone_id=fields.Many2one('commission.zone',domain="[('region_id','=',region_id)]")
    sim_count=fields.Integer(compute='_compute');monetized_count=fields.Integer(compute='_compute');purchase_cost=fields.Monetary(compute='_compute');reported=fields.Monetary(compute='_compute');expected=fields.Monetary(compute='_compute');margin=fields.Monetary(compute='_compute');roi_realized=fields.Float(compute='_compute');roi_expected=fields.Float(compute='_compute');difference=fields.Monetary(compute='_compute');monetization_rate=fields.Float(compute='_compute');currency_id=fields.Many2one('res.currency',default=lambda s:s.env.company.currency_id.id)
    @api.depends('date_from','date_to','commission_date_to','region_id','zone_id')
    def _compute(self):
        Sim=self.env['commission.sim'];Line=self.env['commission.settlement.line']
        for r in self:
            sd=[]
            if r.date_from:sd.append(('purchase_date','>=',r.date_from))
            if r.date_to:sd.append(('purchase_date','<=',r.date_to))
            if r.region_id:sd.append(('region_id','=',r.region_id.id))
            if r.zone_id:sd.append(('zone_id','=',r.zone_id.id))
            sims=Sim.search(sd); sim_ids=sims.ids; cost=sum(sims.mapped('purchase_cost'))
            ld=[('sim_id','in',sim_ids)] if sim_ids else [('id','=',0)]
            if r.commission_date_to:ld.append(('compensation_date','<=',r.commission_date_to))
            agg=Line.read_group(ld,['reported_value:sum','expected_value:sum'],[]) if sim_ids else []
            a=agg[0] if agg else {};reported=a.get('reported_value',0) or 0;expected=a.get('expected_value',0) or 0
            monetized=Line.read_group(ld+[('reported_value','!=',0)],['sim_id'],['sim_id'],lazy=False) if sim_ids else []
            r.sim_count=len(sims);r.monetized_count=len(monetized);r.purchase_cost=cost;r.reported=reported;r.expected=expected;r.margin=reported-cost;r.roi_realized=((reported-cost)/cost*100) if cost else 0;r.roi_expected=((expected-cost)/cost*100) if cost else 0;r.difference=reported-expected;r.monetization_rate=(r.monetized_count/r.sim_count*100) if r.sim_count else 0
