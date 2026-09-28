from collections import defaultdict
from odoo import api, fields, models, _
from odoo.exceptions import UserError

class CommissionSettlementBatch(models.Model):
    _name='commission.settlement.batch'; _description='Liquidación de Operador'; _inherit=['mail.thread']; _order='id desc'
    name=fields.Char(default=lambda s:s.env['ir.sequence'].next_by_code('commission.settlement.batch'),required=True,copy=False)
    operator_id=fields.Many2one('commission.operator',required=True,index=True); period=fields.Char(required=True)
    state=fields.Selection([('draft','Borrador'),('processed','Procesado'),('closed','Cerrado')],default='draft',tracking=True)
    line_ids=fields.One2many('commission.settlement.line','batch_id'); file_ids=fields.One2many('commission.import.file','settlement_batch_id')
    line_count=fields.Integer(compute='_totals'); reported_total=fields.Monetary(compute='_totals'); expected_total=fields.Monetary(compute='_totals'); difference_total=fields.Monetary(compute='_totals')
    currency_id=fields.Many2one('res.currency',default=lambda s:s.env.company.currency_id.id)
    def _totals(self):
        Line=self.env['commission.settlement.line']
        for r in self:
            agg=Line.read_group([('batch_id','=',r.id)], ['reported_value:sum','expected_value:sum','difference:sum'], []) if r.id else []
            a=agg[0] if agg else {}
            r.line_count=Line.search_count([('batch_id','=',r.id)]) if r.id else 0
            r.reported_total=a.get('reported_value',0) or 0; r.expected_total=a.get('expected_value',0) or 0; r.difference_total=a.get('difference',0) or 0

    def action_recalculate(self):
        for batch in self:
            batch.line_ids._recalculate_expected_bulk(batch)
        return True

    def action_close(self):
        self.write({'state':'closed'})

class CommissionImportFile(models.Model):
    _name='commission.import.file'; _description='Archivo Fuente Importado'; _order='id desc'
    name=fields.Char(required=True); sha256=fields.Char(index=True); attachment_id=fields.Many2one('ir.attachment',ondelete='set null'); settlement_batch_id=fields.Many2one('commission.settlement.batch',ondelete='cascade'); purchase_batch_id=fields.Many2one('commission.purchase.batch',ondelete='cascade'); row_count=fields.Integer(); imported_at=fields.Datetime(default=fields.Datetime.now); imported_by=fields.Many2one('res.users',default=lambda s:s.env.user)
    _sql_constraints=[('sha_unique','unique(sha256)','Este archivo ya fue importado anteriormente.')]

class CommissionSettlementLine(models.Model):
    _name='commission.settlement.line'; _description='Detalle de Comisión'; _order='compensation_date desc,id desc'
    batch_id=fields.Many2one('commission.settlement.batch',required=True,ondelete='cascade',index=True)
    sim_id=fields.Many2one('commission.sim',index=True,ondelete='set null'); icc=fields.Char(index=True); icc_key=fields.Char(index=True)
    compensation_date=fields.Date(index=True); region_text=fields.Char(index=True); region_id=fields.Many2one('commission.region',index=True); zone_id=fields.Many2one('commission.zone',index=True)
    customer=fields.Char(); product=fields.Char(index=True); concept=fields.Char(index=True); service_number=fields.Char(index=True)
    activation_date=fields.Date(index=True); regularization_date=fields.Date(); high_date=fields.Date(); distributor_type=fields.Char(); invoice=fields.Char()
    pvp=fields.Monetary(); reported_percentage=fields.Float(digits=(16,4)); recharges=fields.Monetary(); consumptions=fields.Monetary(); base_tariff=fields.Monetary(); evaluated_consumption=fields.Monetary(); reported_value=fields.Monetary(); discounted_base_tariff=fields.Monetary(); advance_value=fields.Monetary()
    scheme_line_id=fields.Many2one('commission.scheme.line',index=True); expected_percentage=fields.Float(digits=(16,4)); expected_value=fields.Monetary(); difference=fields.Monetary(index=True)
    reconciliation_state=fields.Selection([('ok','OK'),('no_rule','Sin regla'),('difference','Diferencia'),('no_purchase','ICC sin compra')],default='no_rule',index=True)
    source_file=fields.Char(index=True); source_row=fields.Integer(); currency_id=fields.Many2one('res.currency',default=lambda s:s.env.company.currency_id.id)
    _sql_constraints=[('source_row_unique','unique(batch_id, source_file, source_row)','La fila fuente ya existe en esta liquidación.')]

    @staticmethod
    def _base_value(line, rule):
        return {'consumption':line.evaluated_consumption,'consumptions':line.consumptions,'recharges':line.recharges,'tariff':line.base_tariff}.get(rule.base_field,0) or 0

    def _recalculate_expected_bulk(self, batch=None):
        """Recalcula sin consultas por fila. Diseñado para cientos de miles de movimientos."""
        records=self
        if batch and not records:
            records=self.search([('batch_id','=',batch.id)])
        if not records: return
        batches=records.mapped('batch_id')
        Rule=self.env['commission.scheme.line']
        rules_by_operator=defaultdict(list)
        for b in batches:
            rules=Rule.search([('scheme_id.operator_id','=',b.operator_id.id),('scheme_id.state','=','active'),('active','=',True)], order='priority,id')
            rules_by_operator[b.operator_id.id]=rules
        updates=[]
        for r in records:
            vals={'scheme_line_id':False,'expected_percentage':0.0,'expected_value':0.0,'difference':r.reported_value or 0.0}
            if not r.sim_id:
                vals['reconciliation_state']='no_purchase'; updates.append((r,vals)); continue
            date=r.compensation_date or fields.Date.today(); concept=(r.concept or '').lower()
            chosen=False
            for rule in rules_by_operator[r.batch_id.operator_id.id]:
                s=rule.scheme_id
                if s.date_from and date < s.date_from: continue
                if s.date_to and date > s.date_to: continue
                pattern=(rule.match_pattern or rule.concept_code or rule.concept_name or '').lower().strip()
                if pattern not in ('','*') and pattern not in concept: continue
                base=self._base_value(r,rule)
                if base < rule.min_amount: continue
                if not rule.no_upper_limit and rule.max_amount and base > rule.max_amount: continue
                chosen=rule; break
            if not chosen:
                vals['reconciliation_state']='no_rule'; updates.append((r,vals)); continue
            base=self._base_value(r,chosen); expected=(base*chosen.percentage/100.0) if chosen.calculation_type=='percentage' else chosen.fixed_amount
            diff=(r.reported_value or 0.0)-expected
            vals.update({'scheme_line_id':chosen.id,'expected_percentage':chosen.percentage,'expected_value':expected,'difference':diff,'reconciliation_state':'ok' if abs(diff)<0.011 else 'difference'})
            updates.append((r,vals))
        # write per record avoids recompute chains; still much cheaper than N rule searches.
        for rec,vals in updates: rec.write(vals)
