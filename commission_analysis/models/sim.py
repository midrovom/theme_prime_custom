from odoo import api, fields, models

class CommissionSim(models.Model):
    _name = 'commission.sim'
    _description = 'SIM / ICC'
    _inherit = ['mail.thread']
    _rec_name = 'icc'
    _order = 'purchase_date desc, id desc'
    icc = fields.Char(required=True, index=True, tracking=True)
    icc_key = fields.Char(index=True, help='Clave normalizada para cruces entre archivos (18 primeros dígitos).')
    operator_id = fields.Many2one('commission.operator', index=True)
    product = fields.Char(index=True)
    purchase_date = fields.Date(index=True)
    invoice = fields.Char(index=True)
    warehouse = fields.Char(index=True)
    region_id = fields.Many2one('commission.region', index=True)
    zone_id = fields.Many2one('commission.zone', index=True)
    purchase_cost = fields.Monetary()
    currency_id = fields.Many2one('res.currency', default=lambda s:s.env.company.currency_id.id)
    purchase_line_ids = fields.One2many('commission.purchase.line','sim_id')
    commission_line_ids = fields.One2many('commission.settlement.line','sim_id')
    realized_commission = fields.Monetary(compute='_compute_kpis')
    expected_commission = fields.Monetary(compute='_compute_kpis')
    margin_realized = fields.Monetary(compute='_compute_kpis')
    roi_realized = fields.Float(compute='_compute_kpis', digits=(16,2))
    roi_expected = fields.Float(compute='_compute_kpis', digits=(16,2))
    monetized = fields.Boolean(compute='_compute_kpis')

    _sql_constraints=[('icc_uniq','unique(icc)','El ICC/SIMCARD ya existe en el maestro de SIM.'),('icc_key_uniq','unique(icc_key)','La clave normalizada del ICC ya existe.')]

    @api.depends('purchase_cost','commission_line_ids.reported_value','commission_line_ids.expected_value')
    def _compute_kpis(self):
        for r in self:
            realized=sum(r.commission_line_ids.mapped('reported_value'))
            expected=sum(r.commission_line_ids.mapped('expected_value'))
            cost=r.purchase_cost or 0
            r.realized_commission=realized; r.expected_commission=expected
            r.margin_realized=realized-cost
            r.roi_realized=((realized-cost)/cost*100) if cost else 0
            r.roi_expected=((expected-cost)/cost*100) if cost else 0
            r.monetized=bool(realized)
