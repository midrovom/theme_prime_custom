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
            'version_esquema': '1.35', 'modelos': catalog,
            'relaciones': ['product_id → transcash.inventory.fact.product.id',
                           'snapshot_id → transcash.inventory.snapshot.id',
                           'company_id → res.company.id'],
            'restriccion_obligatoria': 'Toda consulta se limita a snapshot_id y company_id autorizados por Odoo.',
            'meses_disponibles': json.loads(snapshot.relational_months or '[]'),
            'valores_ejemplo_en_odoo': examples,
            'no_disponible': ['Utilidad neta después de gastos','Stock histórico de cierre',
                              'Trazabilidad de lotes desde compra hasta venta',
                              'Conversión universal de cajas/piezas/m²'],
            'filtros_validados': 'categoria, marca, formato y proveedor_ficha: coincidencia exacta contra el catálogo; en consultas por proveedor real solo compras de movimiento.',
            'indicadores_derivados_por_sku': {
                'descripcion': 'transcash.inventory.fact.product.name',
                'ultima_compra': 'MAX(transcash.inventory.fact.purchase.mes) por SKU en todo el historial de la versión',
                'ultima_venta': 'MAX(transcash.inventory.fact.sale.mes) por SKU en todo el historial de la versión',
                'granularidad': 'YYYY-MM, no día ni número de factura',
            },
            'filtros_numericos': {'stock_unidades': 'Cantidad física de cada SKU al corte actual; NO valor monetario de stock. Las comparaciones <, <=, >, >=, = se combinan con AND y se aplican antes de LIMIT y ORDER BY.'},
            'glosario_de_consultas': {
                'porcelanatos': 'categoria = PORCELANATO, valor canónico resuelto contra catálogo',
                'ceramicas': 'categoria = CERAMICA; nunca sustituye PORCELANATO',
                'stock en unidades': 'transcash.inventory.fact.product.stock_unidades (cantidad física, no USD)',
                'stock menor a cien y mayor a cero': 'dos filtros acumulativos: stock_unidades < 100 AND stock_unidades > 0',
                'lista de productos': 'group_by = sku; incluir descripcion, marca, formato, proveedor, stock_unidades',
                'compra/venta última': 'MAX(mes), YYYY-MM, de tablas de movimiento filtradas por empresa y versión',
            },
            'ejemplo_de_plan': {
                'pregunta': 'Dame una lista de porcelanatos que el stock en unidades sea menor a 100 y mayor a 0',
                'dimension': 'sku', 'categoria': 'PORCELANATO',
                'metrica': 'stock_unidades',
                'stock_conditions': [{'operator': '<', 'value': 100},
                                     {'operator': '>', 'value': 0}],
                'resultado': 'SKU y descripción, con filtros AND estrictos sobre stock físico',
            },
            'regla': 'Los datos de Odoo son fuente de verdad. Devuelve un plan tipado; '
                     'el servidor genera SQL SELECT parametrizado y ejecuta los agregados.'}
