from odoo import fields, models
class CommissionPurchaseBatch(models.Model):
    _name='commission.purchase.batch'; _description='Lote de Compras'; _inherit=['mail.thread']; _order='id desc'
    name=fields.Char(default=lambda s:s.env['ir.sequence'].next_by_code('commission.purchase.batch'), required=True, copy=False)
    period=fields.Char(help='Etiqueta libre, p.ej. OCT-2024'); state=fields.Selection([('draft','Borrador'),('processed','Procesado')],default='draft')
    line_ids=fields.One2many('commission.purchase.line','batch_id'); file_ids=fields.One2many('commission.import.file','purchase_batch_id')
    line_count=fields.Integer(compute='_compute_totals'); total_cost=fields.Monetary(compute='_compute_totals'); currency_id=fields.Many2one('res.currency',default=lambda s:s.env.company.currency_id.id)
    def _compute_totals(self):
        Line=self.env['commission.purchase.line']
        for r in self:
            agg=Line.read_group([('batch_id','=',r.id)],['cost:sum'],[]) if r.id else []
            r.line_count=Line.search_count([('batch_id','=',r.id)]) if r.id else 0; r.total_cost=(agg[0].get('cost',0) if agg else 0) or 0

class CommissionPurchaseLine(models.Model):
    _name='commission.purchase.line'; _description='Detalle de Compra de SIM'; _order='date desc,id desc'
    batch_id=fields.Many2one('commission.purchase.batch',required=True,ondelete='cascade',index=True); sim_id=fields.Many2one('commission.sim',index=True,ondelete='restrict'); icc=fields.Char(required=True,index=True); icc_key=fields.Char(index=True)
    date=fields.Date(index=True); document_type=fields.Char(); number=fields.Char(); supplier_code=fields.Char(); supplier_name=fields.Char(index=True); invoice=fields.Char(index=True); warehouse_code=fields.Char(); warehouse_name=fields.Char(index=True); product_code=fields.Char(); product_name=fields.Char(index=True)
    quantity=fields.Float(default=1); cost=fields.Monetary(); discount=fields.Monetary(); tax=fields.Monetary(); region_id=fields.Many2one('commission.region',index=True); zone_id=fields.Many2one('commission.zone',index=True); source_file=fields.Char(index=True); source_row=fields.Integer(); currency_id=fields.Many2one('res.currency',default=lambda s:s.env.company.currency_id.id)
    _sql_constraints=[('source_row_unique','unique(batch_id, source_file, source_row)','La fila fuente ya existe en este lote de compras.')]
