from collections import defaultdict

from odoo import fields, models, _
from odoo.exceptions import UserError


class CommissionPurchaseBatch(models.Model):
    _name = 'commission.purchase.batch'
    _description = 'Lote de Compras'
    _inherit = ['mail.thread']
    _order = 'id desc'

    name = fields.Char(
        default=lambda self: self.env['ir.sequence'].next_by_code('commission.purchase.batch'),
        required=True, copy=False,
    )
    operator_id = fields.Many2one('commission.operator', required=True, index=True, tracking=True)
    period = fields.Char(help='Etiqueta libre, p.ej. OCT-2024')
    roi_cost_basis = fields.Selection(
        related='operator_id.roi_cost_basis', string='Base de costo ROI', readonly=True
    )
    state = fields.Selection(
        [('draft', 'Borrador'), ('processed', 'Procesado'), ('closed', 'Cerrado')],
        default='draft', tracking=True,
    )
    line_ids = fields.One2many('commission.purchase.line', 'batch_id')
    file_ids = fields.One2many('commission.import.file', 'purchase_batch_id')
    line_count = fields.Integer(compute='_compute_totals', string='Registros')
    total_cost = fields.Monetary(compute='_compute_totals', string='Costo fuente total')
    total_discount = fields.Monetary(compute='_compute_totals', string='Descuento total')
    total_tax = fields.Monetary(compute='_compute_totals', string='Impuesto total')
    total_gross_cost = fields.Monetary(compute='_compute_totals', string='Costo + impuesto neto')
    total_roi_cost = fields.Monetary(compute='_compute_totals', string='Inversión usada para ROI')
    currency_id = fields.Many2one(
        'res.currency', default=lambda self: self.env.company.currency_id.id
    )

    def _compute_totals(self):
        Line = self.env['commission.purchase.line']
        for rec in self:
            if not rec.id:
                rec.line_count = 0
                rec.total_cost = rec.total_discount = rec.total_tax = 0.0
                rec.total_gross_cost = rec.total_roi_cost = 0.0
                continue
            group = Line.read_group(
                [('batch_id', '=', rec.id)],
                ['cost:sum', 'discount:sum', 'tax:sum'],
                [],
            )
            values = group[0] if group else {}
            rec.line_count = Line.search_count([('batch_id', '=', rec.id)])
            rec.total_cost = values.get('cost', 0.0) or 0.0
            rec.total_discount = values.get('discount', 0.0) or 0.0
            rec.total_tax = values.get('tax', 0.0) or 0.0
            rec.total_gross_cost = rec.total_cost - rec.total_discount + rec.total_tax
            rec.total_roi_cost = rec.operator_id._roi_cost_value(
                rec.total_cost, rec.total_discount, rec.total_tax
            ) if rec.operator_id else rec.total_cost

    def write(self, vals):
        if 'operator_id' in vals:
            Line = self.env['commission.purchase.line']
            ImportFile = self.env['commission.import.file']
            for rec in self:
                if rec.operator_id.id != vals.get('operator_id'):
                    has_data = (
                        bool(Line.search([('batch_id', '=', rec.id)], limit=1))
                        or bool(ImportFile.search([('purchase_batch_id', '=', rec.id)], limit=1))
                    )
                    if has_data:
                        raise UserError(_(
                            'No se puede cambiar el operador de un lote de compras que ya contiene archivos o registros.'
                        ))
        return super().write(vals)

    def _refresh_purchase_master_for_sims(self, sim_ids):
        """Sincroniza los datos maestros de la SIM desde su compra más antigua."""
        ids = list(set(sim_ids or []))
        if not ids:
            return True
        self.env['commission.purchase.line'].flush_model([
            'sim_id', 'date', 'invoice', 'warehouse_name', 'product_name', 'region_id', 'zone_id',
        ])
        self.env['commission.sim'].flush_model([
            'purchase_date', 'invoice', 'warehouse', 'product', 'region_id', 'zone_id',
        ])
        self.env.cr.execute(
            """
            WITH first_purchase AS (
                SELECT DISTINCT ON (pl.sim_id)
                       pl.sim_id, pl.date, pl.invoice, pl.warehouse_name, pl.product_name,
                       pl.region_id, pl.zone_id
                  FROM commission_purchase_line pl
                 WHERE pl.sim_id = ANY(%s)
                 ORDER BY pl.sim_id, pl.date NULLS LAST, pl.id
            )
            UPDATE commission_sim s
               SET purchase_date = fp.date,
                   invoice = fp.invoice,
                   warehouse = fp.warehouse_name,
                   product = fp.product_name,
                   region_id = COALESCE(fp.region_id, s.region_id),
                   zone_id = COALESCE(fp.zone_id, s.zone_id)
              FROM first_purchase fp
             WHERE s.id = fp.sim_id
            """,
            (ids,),
        )
        self.env['commission.sim'].invalidate_model([
            'purchase_date', 'invoice', 'warehouse', 'product', 'region_id', 'zone_id'
        ])
        return True

    def _recalculate_roi_cost_for_sims(self, sim_ids):
        """Recompute SIM investment cost from raw purchase lines using the operator setting."""
        self.ensure_one()
        ids = list(set(sim_ids or []))
        if not ids:
            return True
        self.env['commission.purchase.line'].flush_model([
            'sim_id', 'cost', 'discount', 'tax',
        ])
        self.env['commission.sim'].flush_model(['purchase_cost'])
        basis = self.operator_id.roi_cost_basis or 'cost'
        expressions = {
            'cost': 'COALESCE(pl.cost, 0)',
            'net': 'COALESCE(pl.cost, 0) - COALESCE(pl.discount, 0)',
            'gross': 'COALESCE(pl.cost, 0) - COALESCE(pl.discount, 0) + COALESCE(pl.tax, 0)',
        }
        expression = expressions.get(basis, expressions['cost'])
        self.env.cr.execute(
            f"""
            WITH agg AS (
                SELECT pl.sim_id, SUM({expression}) AS roi_cost
                  FROM commission_purchase_line pl
                 WHERE pl.sim_id = ANY(%s)
                 GROUP BY pl.sim_id
            )
            UPDATE commission_sim s
               SET purchase_cost = COALESCE(a.roi_cost, 0)
              FROM agg a
             WHERE s.id = a.sim_id
            """,
            (ids,),
        )
        self.env['commission.sim'].invalidate_model(['purchase_cost'])
        return True

    def action_recalculate_roi_cost(self):
        """Apply the current operator ROI cost basis to SIMs contained in this purchase batch."""
        Sim = self.env['commission.sim']
        for batch in self:
            self.env.cr.execute(
                "SELECT DISTINCT sim_id FROM commission_purchase_line WHERE batch_id=%s AND sim_id IS NOT NULL",
                (batch.id,),
            )
            sim_ids = [row[0] for row in self.env.cr.fetchall()]
            for start in range(0, len(sim_ids), 10000):
                chunk = sim_ids[start:start + 10000]
                batch._refresh_purchase_master_for_sims(chunk)
                batch._recalculate_roi_cost_for_sims(chunk)
                Sim._refresh_kpis(chunk)
        return True

    def action_apply_mappings(self):
        """Reapply Bodega -> Región/Zona after users modify the mapping table."""
        Mapping = self.env['commission.warehouse.mapping']
        Line = self.env['commission.purchase.line']
        mappings = Mapping.search([('active', '=', True)])
        by_code = {}
        by_name = {}
        for mapping in mappings.sorted('id'):
            if mapping.warehouse_code:
                by_code.setdefault(str(mapping.warehouse_code).strip().casefold(), mapping)
            if mapping.warehouse_name:
                by_name.setdefault(str(mapping.warehouse_name).strip().casefold(), mapping)

        for batch in self:
            last_id = 0
            while True:
                lines = Line.search(
                    [('batch_id', '=', batch.id), ('id', '>', last_id)],
                    order='id', limit=5000,
                )
                if not lines:
                    break
                groups = defaultdict(list)
                for line in lines:
                    code = str(line.warehouse_code or '').strip().casefold()
                    name = str(line.warehouse_name or '').strip().casefold()
                    mapping = by_code.get(code) or by_name.get(name)
                    if mapping:
                        groups[(mapping.region_id.id, mapping.zone_id.id)].append(line.id)

                for (region_id, zone_id), line_ids in groups.items():
                    # SQL avoids individual ORM writes while the 5k window bounds memory use.
                    self.env.cr.execute(
                        "UPDATE commission_purchase_line SET region_id=%s, zone_id=%s WHERE id = ANY(%s)",
                        (region_id, zone_id, line_ids),
                    )
                    self.env.cr.execute(
                        """
                        UPDATE commission_sim s
                           SET region_id=%s, zone_id=%s
                         WHERE s.id IN (
                             SELECT DISTINCT sim_id FROM commission_purchase_line
                              WHERE id = ANY(%s) AND sim_id IS NOT NULL
                         )
                        """,
                        (region_id, zone_id, line_ids),
                    )
                last_id = lines[-1].id
            Line.invalidate_model(['region_id', 'zone_id'])
            Sim = self.env['commission.sim']
            Sim.invalidate_model(['region_id', 'zone_id'])

            # Mantener la geografía de las liquidaciones alineada con el maestro SIM.
            self.env['commission.settlement.line']._match_sims_bulk(
                operator_id=batch.operator_id.id,
            )
        return True

    def action_close(self):
        self.write({'state': 'closed'})
        return True


class CommissionPurchaseLine(models.Model):
    _name = 'commission.purchase.line'
    _description = 'Detalle de Compra de SIM'
    _order = 'date desc, id desc'

    batch_id = fields.Many2one(
        'commission.purchase.batch', required=True, ondelete='cascade', index=True
    )
    operator_id = fields.Many2one(
        'commission.operator', related='batch_id.operator_id', store=True, index=True
    )
    sim_id = fields.Many2one('commission.sim', index=True, ondelete='restrict')
    icc = fields.Char(required=True, index=True)
    icc_key = fields.Char(index=True)
    date = fields.Date(index=True)
    document_type = fields.Char()
    number = fields.Char()
    supplier_code = fields.Char()
    supplier_name = fields.Char(index=True)
    invoice = fields.Char(index=True)
    warehouse_code = fields.Char(index=True)
    warehouse_name = fields.Char(index=True)
    product_code = fields.Char()
    product_name = fields.Char(index=True)
    quantity = fields.Float(default=1)
    cost = fields.Monetary()
    discount = fields.Monetary()
    tax = fields.Monetary()
    region_id = fields.Many2one('commission.region', index=True)
    zone_id = fields.Many2one('commission.zone', index=True)
    source_file = fields.Char(index=True)
    source_row = fields.Integer()
    currency_id = fields.Many2one(
        'res.currency', default=lambda self: self.env.company.currency_id.id
    )

    _sql_constraints = [
        (
            'source_row_unique',
            'unique(batch_id, source_file, source_row)',
            'La fila fuente ya existe en este lote de compras.',
        )
    ]
