# -*- coding: utf-8 -*-
"""Dynamic data dictionary from registered Odoo models (not Excel headings)."""
import json

MODEL_NAMES = [
    'transcash.inventory.fact.product',
    'transcash.inventory.fact.sale',
    'transcash.inventory.fact.purchase',
    'transcash.inventory.fact.supplier.purchase',
    'transcash.inventory.fact.stock',
]
# Explicit columns available to the LLM, with business meaning, not secrets.
ALLOWED = {
    MODEL_NAMES[0]: ('snapshot_id','company_id','sku','name','categoria','marca','formato',
                     'proveedor_ficha','costo_unitario','precio_venta','stock_unidades','stock_valor'),
    MODEL_NAMES[1]: ('snapshot_id','company_id','product_id','mes','cantidad_vendida','ventas','costo_ventas'),
    MODEL_NAMES[2]: ('snapshot_id','company_id','product_id','mes','cantidad_comprada','compras'),
    MODEL_NAMES[3]: ('snapshot_id','company_id','product_id','mes','proveedor_compra','compras'),
    MODEL_NAMES[4]: ('snapshot_id','company_id','product_id','bodega','cantidad'),
}


def schema_context(env, snapshot):
    """Only exposed models, no sensitive Odoo user/partner/access-token tables."""
    catalog = {}
    for name in MODEL_NAMES:
        model = env[name]
        cols = {}
        for fieldname in ALLOWED[name]:
            field = model._fields[fieldname]
            cols[fieldname] = {'tipo': field.type, 'descripcion': str(field.string),
                               'relacion': getattr(field, 'comodel_name', None) or ''}
        catalog[name] = {'tabla_sql': model._table, 'campos': cols}
    cr = env.cr
    examples = {}
    for field in ('categoria','marca','formato','proveedor_ficha'):
        cr.execute('''SELECT "''' + field + '''", COUNT(*) FROM transcash_inventory_fact_product
                     WHERE snapshot_id=%s AND company_id=%s
                     GROUP BY "''' + field + '''" ORDER BY COUNT(*) DESC LIMIT 25''',
                   (snapshot.id, snapshot.company_id.id))
        examples[field] = [item[0] for item in cr.fetchall() if item[0]]
    cr.execute('SELECT DISTINCT bodega FROM transcash_inventory_fact_stock WHERE snapshot_id=%s AND company_id=%s ORDER BY bodega LIMIT 30', (snapshot.id, snapshot.company_id.id))
    examples['bodegas'] = [r[0] for r in cr.fetchall()]
    return {'origen': 'Tablas SQL PostgreSQL persistidas y administradas por Odoo 18',
            'version_esquema': '1.15', 'modelos': catalog,
            'relaciones': ['product_id → transcash.inventory.fact.product.id',
                           'snapshot_id → transcash.inventory.snapshot.id',
                           'company_id → res.company.id'],
            'restriccion_obligatoria': 'Toda consulta se limita a snapshot_id y company_id autorizados por Odoo.',
            'meses_disponibles': json.loads(snapshot.relational_months or '[]'),
            'valores_ejemplo_en_odoo': examples,
            'no_disponible': ['Utilidad neta después de gastos','Stock histórico de cierre',
                              'Trazabilidad de lotes desde compra hasta venta',
                              'Conversión universal de cajas/piezas/m²'],
            'regla': 'Los datos de Odoo son fuente de verdad. Devuelve un plan tipado; '
                     'el servidor genera SQL SELECT parametrizado y ejecuta los agregados.'}
