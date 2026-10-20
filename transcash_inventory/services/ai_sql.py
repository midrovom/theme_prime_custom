# -*- coding: utf-8 -*-
"""Trusted SQL compiler for natural-language inventory analytics.

OpenAI produces a TYPED PLAN, not SQL. Only this module creates SELECT text.
The SELECT is always restricted by company_id and snapshot_id using parameters.
"""
import collections
import json
import re

from .ai_analytics import METRICS, DIMENSIONS, BASE_FIELDS, _formula, _metrics

# Constant Odoo tables and pre-approved dimensions. No table or column name ever
# comes from the model, query string or HTTP request.
PRODUCT_TABLE = 'transcash_inventory_fact_product'
SALES_TABLE = 'transcash_inventory_fact_sale'
PURCHASE_TABLE = 'transcash_inventory_fact_purchase'
SUPPLIER_TABLE = 'transcash_inventory_fact_supplier_purchase'
STOCK_TABLE = 'transcash_inventory_fact_stock'

GROUP_COLUMNS = {
    'total': "'TOTAL'",
    'sku': "fp.sku || ' · ' || LEFT(fp.name, 100)",
    'categoria': 'fp.categoria',
    'marca': 'fp.marca',
    'formato': 'fp.formato',
    'proveedor_ficha': 'fp.proveedor_ficha',
    'marca_formato': "CONCAT_WS(' / ', fp.marca, fp.formato)",
    'categoria_formato': "CONCAT_WS(' / ', fp.categoria, fp.formato)",
    'categoria_marca': "CONCAT_WS(' / ', fp.categoria, fp.marca)",
    'categoria_marca_formato': "CONCAT_WS(' / ', fp.categoria, fp.marca, fp.formato)",
    'proveedor_formato': "CONCAT_WS(' / ', fp.proveedor_ficha, fp.formato)",
    'proveedor_categoria_marca_formato': "CONCAT_WS(' / ', fp.proveedor_ficha, fp.categoria, fp.marca, fp.formato)",
}

SQL_METRIC_COLUMNS = ('ventas', 'costo_ventas', 'cantidad_vendida', 'compras',
                      'cantidad_comprada', 'stock_unidades', 'stock_valor')
SQL_TOTAL_EXPR = ',\n '.join('COALESCE(SUM({}),0) AS {}'.format(col, col) for col in SQL_METRIC_COLUMNS)


def _contains(expr, value, params):
    params.append(str(value)[:120])
    return 'POSITION(LOWER(%s) IN LOWER(COALESCE({},\'\'))) > 0'.format(expr)


def build_select(snapshot_id, company_id, plan, months, default_start=None, default_end=None):
    if not isinstance(plan, dict):
        raise ValueError('Plan SQL no válido.')
    dim = str(plan.get('group_by') or 'total')
    metric = str(plan.get('metric') or 'ventas')
    metrics = plan.get('metrics') or [metric]
    if dim not in GROUP_COLUMNS and dim not in ('mes', 'proveedor_compra', 'bodega'):
        raise ValueError('Dimensión desconocida; SQL no generado.')
    if metric not in METRICS and metric != 'formula':
        raise ValueError('Métrica desconocida; SQL no generado.')
    if not isinstance(metrics, list) or not 1 <= len(metrics) <= 8 or len(set(metrics)) != len(metrics):
        raise ValueError('Se requieren entre 1 y 8 métricas diferentes.')
    if metric not in metrics or any(m not in METRICS and m != 'formula' for m in metrics):
        raise ValueError('Métrica de SQL no autorizada.')
    if dim == 'proveedor_compra' and any(m != 'compras' for m in metrics):
        raise ValueError('Solo están disponibles las compras por proveedor real; no hay trazabilidad de ventas por proveedor de abastecimiento.')
    if dim == 'bodega' and any(m not in ('stock_unidades', 'stock_valor') for m in metrics):
        raise ValueError('Por bodega solo existe stock al corte, no ventas ni compras por ubicación.')
    if dim == 'mes' and any(m in ('stock_unidades', 'stock_valor') for m in metrics):
        raise ValueError('No existe stock histórico mensual; no se puede sumar stock de cierre por mes.')
    if not months:
        raise ValueError('No hay períodos registrados en Odoo.')
    start = str(plan.get('desde') or default_start or months[max(0,len(months)-12)])
    end = str(plan.get('hasta') or default_end or months[-1])
    if start not in months or end not in months or months.index(start) > months.index(end):
        raise ValueError('El intervalo solicitado no existe en la versión de Odoo.')
    top_n = min(50, max(1, int(plan.get('top_n') or 15)))
    filters = {key: str(plan.get(key) or '').strip()[:120] for key in
               ('categoria', 'marca', 'formato', 'proveedor', 'sku')}
    params = [int(snapshot_id), int(company_id)]
    constraints = ['fp.snapshot_id = %s', 'fp.company_id = %s']
    for field in ('categoria', 'marca'):
        if filters[field]:
            constraints.append(_contains('fp.' + field, filters[field], params))
    if filters['formato']:
        # Normalizes 45*45, 45×45 and 45x45 consistently; no SQL wildcards.
        normalize_sql = "REPLACE(REPLACE(REPLACE(LOWER(fp.formato),'×','x'),'*','x'),' ','')"
        normalized_value = filters['formato'].lower().replace('×','x').replace('*','x').replace(' ','')
        constraints.append(_contains(normalize_sql, normalized_value, params))
    if filters['sku']:
        params.extend([filters['sku'], filters['sku']])
        constraints.append("(POSITION(LOWER(%s) IN LOWER(fp.sku)) > 0 OR POSITION(LOWER(%s) IN LOWER(fp.name)) > 0)")
    if filters['proveedor'] and dim != 'proveedor_compra':
        constraints.append(_contains('fp.proveedor_ficha', filters['proveedor'], params))
    count_sql = 'SELECT COUNT(*) FROM ' + PRODUCT_TABLE + ' fp WHERE ' + ' AND '.join(constraints)
    count_params = list(params)
    fp_sql = ('fp AS (SELECT fp.* FROM ' + PRODUCT_TABLE + ' fp WHERE '
              + ' AND '.join(constraints) + ')')
    if dim == 'proveedor_compra':
        supplier_filter = ''
        supplier_params = [start, end]
        if filters['proveedor']:
            supplier_filter = ' AND ' + _contains('sp.proveedor_compra', filters['proveedor'], supplier_params)
        sql = '''WITH {fp_sql}
SELECT sp.proveedor_compra AS grupo,
 0::double precision AS ventas, 0::double precision AS costo_ventas,
 0::double precision AS cantidad_vendida,
 SUM(sp.compras) AS compras, 0::double precision AS cantidad_comprada,
 0::double precision AS stock_unidades, 0::double precision AS stock_valor
FROM {sup} sp JOIN fp ON fp.id=sp.product_id
WHERE sp.snapshot_id=%s AND sp.company_id=%s AND sp.mes BETWEEN %s AND %s {supplier_filter}
GROUP BY sp.proveedor_compra'''.format(fp_sql=fp_sql, sup=SUPPLIER_TABLE, supplier_filter=supplier_filter)
        # Insert scoping params BEFORE supplier dates; order must match SQL.
        params.extend([int(snapshot_id), int(company_id)] + supplier_params)
        count_sql = ('WITH ' + fp_sql + ' SELECT COUNT(DISTINCT sp.product_id) FROM '
                     + SUPPLIER_TABLE + ' sp JOIN fp ON fp.id=sp.product_id '
                     + 'WHERE sp.snapshot_id=%s AND sp.company_id=%s '
                     + 'AND sp.mes BETWEEN %s AND %s ' + supplier_filter)
        count_params = list(params)
    elif dim == 'bodega':
        params.extend([int(snapshot_id), int(company_id)])
        sql = '''WITH {fp_sql}
SELECT st.bodega AS grupo,
 0::double precision AS ventas, 0::double precision AS costo_ventas,
 0::double precision AS cantidad_vendida, 0::double precision AS compras,
 0::double precision AS cantidad_comprada,
 SUM(GREATEST(st.cantidad,0)) AS stock_unidades,
 SUM(GREATEST(st.cantidad,0) * GREATEST(fp.costo_unitario,0)) AS stock_valor
FROM {stock} st JOIN fp ON fp.id=st.product_id
WHERE st.snapshot_id=%s AND st.company_id=%s
GROUP BY st.bodega'''.format(fp_sql=fp_sql, stock=STOCK_TABLE)
    elif dim == 'mes':
        # Month-based measures are computed independently, avoiding the classic
        # M x N double-counting caused by joining sales and purchases directly.
        params.extend([int(snapshot_id), int(company_id), start, end,
                       int(snapshot_id), int(company_id), start, end,
                       months[months.index(start):months.index(end)+1]])
        sql = '''WITH {fp_sql},
s AS (SELECT s.mes, SUM(s.ventas) AS ventas,
 SUM(s.costo_ventas) AS costo_ventas, SUM(s.cantidad_vendida) AS cantidad_vendida
 FROM {sales} s JOIN fp ON fp.id=s.product_id
 WHERE s.snapshot_id=%s AND s.company_id=%s AND s.mes BETWEEN %s AND %s GROUP BY s.mes),
b AS (SELECT b.mes, SUM(b.compras) AS compras,
 SUM(b.cantidad_comprada) AS cantidad_comprada
 FROM {buys} b JOIN fp ON fp.id=b.product_id
 WHERE b.snapshot_id=%s AND b.company_id=%s AND b.mes BETWEEN %s AND %s GROUP BY b.mes),
calendar AS (SELECT UNNEST(%s::text[]) AS mes)
SELECT calendar.mes AS grupo, COALESCE(s.ventas,0) AS ventas,
 COALESCE(s.costo_ventas,0) AS costo_ventas,
 COALESCE(s.cantidad_vendida,0) AS cantidad_vendida,
 COALESCE(b.compras,0) AS compras,
 COALESCE(b.cantidad_comprada,0) AS cantidad_comprada,
 0::double precision AS stock_unidades, 0::double precision AS stock_valor
FROM calendar LEFT JOIN s ON s.mes=calendar.mes LEFT JOIN b ON b.mes=calendar.mes'''.format(
    fp_sql=fp_sql, sales=SALES_TABLE, buys=PURCHASE_TABLE)
    else:
        params.extend([int(snapshot_id), int(company_id), start, end,
                       int(snapshot_id), int(company_id), start, end])
        group_expr = GROUP_COLUMNS[dim]
        sql = '''WITH {fp_sql},
s AS (SELECT s.product_id, SUM(s.ventas) AS ventas,
 SUM(s.costo_ventas) AS costo_ventas, SUM(s.cantidad_vendida) AS cantidad_vendida
 FROM {sales} s JOIN fp ON fp.id=s.product_id
 WHERE s.snapshot_id=%s AND s.company_id=%s AND s.mes BETWEEN %s AND %s GROUP BY s.product_id),
b AS (SELECT b.product_id, SUM(b.compras) AS compras,
 SUM(b.cantidad_comprada) AS cantidad_comprada
 FROM {buys} b JOIN fp ON fp.id=b.product_id
 WHERE b.snapshot_id=%s AND b.company_id=%s AND b.mes BETWEEN %s AND %s GROUP BY b.product_id),
per_product AS (SELECT {grp} AS grupo,
 COALESCE(s.ventas,0) AS ventas,
 COALESCE(s.costo_ventas,0) AS costo_ventas,
 COALESCE(s.cantidad_vendida,0) AS cantidad_vendida,
 COALESCE(b.compras,0) AS compras,
 COALESCE(b.cantidad_comprada,0) AS cantidad_comprada,
 fp.stock_unidades AS stock_unidades, fp.stock_valor AS stock_valor
 FROM fp LEFT JOIN s ON s.product_id=fp.id LEFT JOIN b ON b.product_id=fp.id)
SELECT grupo, {totals} FROM per_product GROUP BY grupo'''.format(
    fp_sql=fp_sql, sales=SALES_TABLE, buys=PURCHASE_TABLE, grp=group_expr,
    totals=SQL_TOTAL_EXPR)
    # There is no user-controlled SQL here: all identifiers originate in constant
    # dictionaries and all filter values are bound params.
    return sql, params, {'dimension': dim, 'metric': metric, 'metrics': metrics,
                          'period': {'desde': start, 'hasta': end}, 'filters': filters,
                          'top_n': top_n, 'descending': plan.get('orden') != 'asc',
                          'formula': str(plan.get('formula') or '').strip(),
                          'count_sql': count_sql, 'count_params': count_params}


def execute_sql_plan(env, snapshot, plan, default_start=None, default_end=None):
    if not snapshot.relational_ready:
        raise ValueError('La base de indicadores de esta versión todavía no está preparada.')
    months = json.loads(snapshot.relational_months or '[]')
    sql, params, info = build_select(snapshot.id, snapshot.company_id.id, plan, months,
                                     default_start, default_end)
    env.cr.execute(sql, params)
    rows = env.cr.fetchall()
    metric, metrics = info['metric'], info['metrics']
    expression = info['formula']
    if 'formula' in metrics and not expression:
        raise ValueError('Debe indicar la expresión del indicador personalizado.')

    def computed(raw):
        data = dict(zip(SQL_METRIC_COLUMNS, [float(n or 0) for n in raw]))
        # SQL columns are pre-aggregated; derived measures are computed *after*
        # summing the money, never by averaging individual percentages.
        data['utilidad'] = data['ventas'] - data['costo_ventas']
        vals = _metrics(data)
        if 'formula' in metrics:
            vals['formula'] = _formula(expression, {f: vals[f] for f in BASE_FIELDS})
        return vals

    evaluated = []
    agg = collections.defaultdict(float)
    for row in rows:
        label = str(row[0])
        vals = computed(row[1:])
        for field, value in zip(SQL_METRIC_COLUMNS, row[1:]):
            agg[field] += float(value or 0)
        target = vals.get(metric)
        if target is None:
            continue
        detail = {k: round(vals[k], 4) if vals[k] is not None else None for k in metrics}
        evaluated.append({'grupo': label, 'valor': round(target, 4), 'metricas': detail,
                          'ventas': round(vals['ventas'], 2), 'utilidad': round(vals['utilidad'], 2),
                          'compras': round(vals['compras'], 2),
                          'margen': round(vals['margen'],2) if vals['margen'] is not None else None,
                          'stock_valor': round(vals['stock_valor'],2)})
    evaluated.sort(key=lambda row: row['valor'], reverse=info['descending'])
    total_vals = computed([agg[k] for k in SQL_METRIC_COLUMNS])
    totals = {m: round(total_vals[m], 4) if total_vals[m] is not None else None for m in metrics}
    env.cr.execute(info['count_sql'], info['count_params'])
    selected_products = int(env.cr.fetchone()[0])
    notes = ['Fuente: tablas relacionales de Odoo (no el Excel ni datos generados por ChatGPT).',
             'Stock es existencia al corte, valorada con costo de catálogo.',
             'No sumar cantidades de distintas unidades (m², cajas, piezas).']
    if info['dimension'] == 'bodega':
        notes.append('No existen ventas históricas por bodega en esta fuente; solo stock al corte.')
    if info['dimension'] == 'proveedor_compra':
        notes.append('Proveedor real de compra: solo importe de compras; no se atribuye rentabilidad por lote.')
    elif info['dimension'] in ('proveedor_ficha', 'proveedor_formato', 'proveedor_categoria_marca_formato'):
        notes.append('Proveedor de catálogo: rentabilidad de cartera, no trazabilidad por lote.')
    if 'formula' in metrics:
        notes.append('Fórmula aritmética validada: ' + expression)
    return {'dimension': info['dimension'], 'metrica': metric, 'metricas': metrics,
            'etiquetas': {m: METRICS.get(m, 'Indicador personalizado: '+expression) for m in metrics},
            'totales': totals, 'etiqueta': METRICS.get(metric, 'Indicador personalizado: '+expression),
            'periodo': info['period'], 'filtros': info['filters'],
            'filas': evaluated[:info['top_n']],
            'total': round(total_vals[metric],4) if total_vals[metric] is not None else None,
            'grupos_evaluados': len(evaluated), 'sku_evaluados': selected_products,
            'observaciones': notes,
            'fuente': 'odoo_sql', 'sql_consulta': sql, 'sql_parametros': params}
