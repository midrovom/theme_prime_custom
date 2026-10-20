# -*- coding: utf-8 -*-
"""Read-only inventory reporting facts, persisted as first-class Odoo models.

They are populated by the SAME ingestion service for XLSX and future API feeds.
The ChatGPT planner only sees their explicitly approved metadata; it is never
allowed to send SQL that the server executes verbatim.
"""
import json
import logging

from psycopg2.extras import execute_values
from odoo import fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class FactProduct(models.Model):
    _name = 'transcash.inventory.fact.product'
    _description = 'Inventario: catálogo normalizado por versión'
    _order = 'sku'

    snapshot_id = fields.Many2one('transcash.inventory.snapshot', required=True, ondelete='cascade', index=True)
    company_id = fields.Many2one('res.company', required=True, index=True)
    sku = fields.Char(required=True, index=True)
    name = fields.Char(required=True)
    categoria = fields.Char(index=True)
    marca = fields.Char(index=True)
    formato = fields.Char(index=True)
    proveedor_ficha = fields.Char(index=True)
    costo_unitario = fields.Float(digits=(20, 5))
    precio_venta = fields.Float(digits=(20, 4))
    stock_unidades = fields.Float(digits=(20, 4))
    stock_valor = fields.Float(digits=(20, 4))

    _sql_constraints = [('sku_snapshot_unique', 'unique(snapshot_id, sku)', 'SKU duplicado en la versión de inventario.')]


class FactSale(models.Model):
    _name = 'transcash.inventory.fact.sale'
    _description = 'Inventario: ventas mensuales normalizadas'
    snapshot_id = fields.Many2one('transcash.inventory.snapshot', required=True, ondelete='cascade', index=True)
    company_id = fields.Many2one('res.company', required=True, index=True)
    product_id = fields.Many2one('transcash.inventory.fact.product', required=True, ondelete='cascade', index=True)
    mes = fields.Char(required=True, index=True)  # YYYY-MM, no día inferido
    cantidad_vendida = fields.Float(digits=(20, 4))
    ventas = fields.Float(digits=(20, 4))
    costo_ventas = fields.Float(digits=(20, 4))


class FactPurchase(models.Model):
    _name = 'transcash.inventory.fact.purchase'
    _description = 'Inventario: compras mensuales por producto'
    snapshot_id = fields.Many2one('transcash.inventory.snapshot', required=True, ondelete='cascade', index=True)
    company_id = fields.Many2one('res.company', required=True, index=True)
    product_id = fields.Many2one('transcash.inventory.fact.product', required=True, ondelete='cascade', index=True)
    mes = fields.Char(required=True, index=True)
    cantidad_comprada = fields.Float(digits=(20, 4))
    compras = fields.Float(digits=(20, 4))


class FactSupplierPurchase(models.Model):
    _name = 'transcash.inventory.fact.supplier.purchase'
    _description = 'Inventario: compras al proveedor real de movimiento'
    snapshot_id = fields.Many2one('transcash.inventory.snapshot', required=True, ondelete='cascade', index=True)
    company_id = fields.Many2one('res.company', required=True, index=True)
    product_id = fields.Many2one('transcash.inventory.fact.product', required=True, ondelete='cascade', index=True)
    mes = fields.Char(required=True, index=True)
    proveedor_compra = fields.Char(required=True, index=True)
    compras = fields.Float(digits=(20, 4))


class FactStock(models.Model):
    _name = 'transcash.inventory.fact.stock'
    _description = 'Inventario: existencia por bodega en el corte'
    snapshot_id = fields.Many2one('transcash.inventory.snapshot', required=True, ondelete='cascade', index=True)
    company_id = fields.Many2one('res.company', required=True, index=True)
    product_id = fields.Many2one('transcash.inventory.fact.product', required=True, ondelete='cascade', index=True)
    bodega = fields.Char(required=True, index=True)
    cantidad = fields.Float(digits=(20, 4))


def _bulk(cr, table, columns, rows, batch=3000):
    if not rows:
        return
    # These table and column names are constants defined by the module, never AI input.
    statement = 'INSERT INTO ' + table + ' (' + ','.join(columns) + ') VALUES %s'
    execute_values(cr._obj if hasattr(cr, '_obj') else cr, statement, rows, page_size=batch)


def materialize_snapshot(snapshot, dataset=None):
    """Create SQL reporting facts atomically for an authorized Odoo snapshot.

    Existing v1.14 snapshots are upgraded lazily upon first AI consultation.
    A single import entry point also materializes all newly imported snapshots.
    Must run inside Odoo's managed transaction (no manual commits).
    """
    snapshot.ensure_one()
    if snapshot.relational_ready:
        return
    cr = snapshot.env.cr
    # Lock is scoped to DB transaction. A concurrent request must retry instead
    # of silently reading a half-built version.
    cr.execute('SELECT pg_try_advisory_xact_lock(%s, %s)', (845231, snapshot.id))
    if not cr.fetchone()[0]:
        raise UserError('La preparación de esta versión ya está en curso. Inténtelo nuevamente en unos segundos.')
    if snapshot.relational_ready:
        return
    if dataset is None:
        dataset = json.loads(snapshot.get_dashboard_json())
    products = dataset['products']
    months = dataset['months']
    company = snapshot.company_id.id
    sid = snapshot.id
    # Snapshot materialization may be retried after an interrupted older import.
    for table in ('transcash_inventory_fact_stock', 'transcash_inventory_fact_supplier_purchase',
                  'transcash_inventory_fact_purchase', 'transcash_inventory_fact_sale'):
        cr.execute('DELETE FROM ' + table + ' WHERE snapshot_id=%s', (sid,))
    cr.execute('DELETE FROM transcash_inventory_fact_product WHERE snapshot_id=%s', (sid,))
    cats, brands, formats, prov = dataset['categories'], dataset['brands'], None, dataset['providers']
    from ..services.ai_analytics import product_format
    product_rows = [(sid, company, str(p[0]), str(p[1]), cats[p[2]], brands[p[3]], product_format(p),
                     prov[p[4]], float(p[5]), float(p[6]), float(p[7]), float(p[7])*max(0.0,float(p[5]))) for p in products]
    _bulk(cr, 'transcash_inventory_fact_product',
          ('snapshot_id', 'company_id', 'sku', 'name', 'categoria', 'marca', 'formato',
           'proveedor_ficha', 'costo_unitario', 'precio_venta', 'stock_unidades', 'stock_valor'), product_rows)
    cr.execute('SELECT id, sku FROM transcash_inventory_fact_product WHERE snapshot_id=%s', (sid,))
    by_sku = {sku: id_ for id_, sku in cr.fetchall()}
    pid = [by_sku[p[0]] for p in products]
    sale_rows = [(sid, company, pid[int(r[0])], months[int(r[1])], float(r[2]), float(r[3]), float(r[4]))
                 for r in dataset['sales']]
    buy_rows = [(sid, company, pid[int(r[0])], months[int(r[1])], float(r[2]), float(r[3]))
                for r in dataset['purchases']]
    supplier_names = dataset.get('purchaseSuppliers') or []
    supplier_rows = [(sid, company, pid[int(r[0])], months[int(r[1])],
                      supplier_names[int(r[2])], float(r[3]))
                     for r in dataset.get('supplierPurchases') or []]
    warehouse_names = dataset.get('warehouses') or []
    stock_rows = [(sid, company, pid[int(r[0])], warehouse_names[int(r[1])], float(r[2]))
                  for r in dataset.get('stockWarehouses') or []]
    _bulk(cr, 'transcash_inventory_fact_sale',
          ('snapshot_id', 'company_id', 'product_id', 'mes', 'cantidad_vendida', 'ventas', 'costo_ventas'), sale_rows)
    _bulk(cr, 'transcash_inventory_fact_purchase',
          ('snapshot_id', 'company_id', 'product_id', 'mes', 'cantidad_comprada', 'compras'), buy_rows)
    _bulk(cr, 'transcash_inventory_fact_supplier_purchase',
          ('snapshot_id', 'company_id', 'product_id', 'mes', 'proveedor_compra', 'compras'), supplier_rows)
    _bulk(cr, 'transcash_inventory_fact_stock',
          ('snapshot_id', 'company_id', 'product_id', 'bodega', 'cantidad'), stock_rows)
    snapshot.sudo().write({'relational_ready': True,
                           'relational_months': json.dumps(months, separators=(',', ':'))})
    _logger.info('Transcash: SQL facts ready snapshot %s: %s products, %s sales, %s purchases, %s suppliers, %s stock',
                 sid, len(product_rows), len(sale_rows), len(buy_rows), len(supplier_rows), len(stock_rows))
