# -*- coding: utf-8 -*-
"""Safe, deterministic inventory aggregation used by the ChatGPT planner.

No model-generated Python/SQL/domain expressions are ever executed.
"""
import ast
import collections
import math
import re
import unicodedata

METRICS = {
    'ventas': 'Ventas netas (USD)', 'utilidad': 'Utilidad bruta (USD)',
    'margen': 'Margen bruto (%)', 'compras': 'Compras (USD)',
    'cantidad_vendida': 'Cantidad vendida', 'cantidad_comprada': 'Cantidad comprada',
    'stock_unidades': 'Stock positivo (cantidad)', 'stock_valor': 'Stock estimado (USD)',
    'costo_ventas': 'Costo de ventas (USD)', 'precio_promedio': 'Precio medio por unidad vendida',
    'descripcion': 'Descripción del producto',
    'ultima_compra': 'Última compra (mes)', 'ultima_venta': 'Última venta (mes)',
    'categoria': 'Categoría', 'marca': 'Marca', 'formato': 'Formato',
    'proveedor_ficha': 'Proveedor del catálogo',
    'costo_unitario': 'Costo unitario de catálogo (USD)',
    'precio_venta': 'Precio de lista (USD)',
}
DIMENSIONS = {
    'total', 'sku', 'categoria', 'marca', 'formato', 'proveedor_ficha',
    'proveedor_compra', 'mes', 'marca_formato', 'categoria_formato',
    'categoria_marca', 'categoria_marca_formato', 'proveedor_formato'
}
BASE_FIELDS = {'ventas', 'utilidad', 'compras', 'cantidad_vendida',
               'cantidad_comprada', 'stock_unidades', 'stock_valor', 'costo_ventas'}


def _norm(value):
    s = unicodedata.normalize('NFKD', str(value or ''))
    return re.sub(r'(\d)\s*[x×*]\s*(\d)', r'\1x\2', ''.join(ch for ch in s if not unicodedata.combining(ch)).casefold()).strip()


def _matches(value, pattern):
    return not pattern or _norm(pattern) in _norm(value)


def _number(value):
    try:
        v = float(value or 0)
        return v if math.isfinite(v) else 0.0
    except (ValueError, TypeError):
        return 0.0


def product_format(p):
    if len(p) > 21 and str(p[21] or '').strip():
        return str(p[21]).strip()
    match = re.search(r'\d{1,4}(?:[.,]\d+)?\s*[x×*]\s*\d{1,4}(?:[.,]\d+)?', p[1] or '', re.I)
    return match.group(0) if match else 'SIN FORMATO'


def _metrics(values):
    d = {key: float(values.get(key, 0.0)) for key in BASE_FIELDS}
    d['margen'] = 100 * d['utilidad'] / d['ventas'] if d['ventas'] else None
    d['precio_promedio'] = d['ventas'] / d['cantidad_vendida'] if d['cantidad_vendida'] else None
    return d


def _formula(expr, values):
    """Whitelist-only arithmetic expression using computed inventory metrics."""
    if not expr or len(expr) > 120:
        raise ValueError('La fórmula está vacía o excede el límite.')
    tree = ast.parse(expr, mode='eval')

    def eval_node(node, depth=0):
        if depth > 15:
            raise ValueError('Fórmula demasiado compleja.')
        if isinstance(node, ast.Expression):
            return eval_node(node.body, depth + 1)
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            if abs(node.value) > 1e10:
                raise ValueError('Constante fuera de rango.')
            return float(node.value)
        if isinstance(node, ast.Name) and node.id in values:
            return float(values[node.id])
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            val = eval_node(node.operand, depth + 1)
            return val if isinstance(node.op, ast.UAdd) else -val
        if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div)):
            a, b = eval_node(node.left, depth + 1), eval_node(node.right, depth + 1)
            if isinstance(node.op, ast.Add):
                result = a + b
            elif isinstance(node.op, ast.Sub):
                result = a - b
            elif isinstance(node.op, ast.Mult):
                result = a * b
            else:
                if b == 0:
                    return None
                result = a / b
            if not math.isfinite(result) or abs(result) > 1e15:
                raise ValueError('Resultado fuera de rango.')
            return result
        raise ValueError('Fórmula no permitida. Solo operadores aritméticos y métricas conocidas.')

    result = eval_node(tree)
    return round(result, 4) if result is not None else None


def execute_plan(dataset, plan, default_start=None, default_end=None):
    if not isinstance(plan, dict):
        raise ValueError('Plan no válido.')
    dimension = str(plan.get('group_by') or 'total').strip()
    metric = str(plan.get('metric') or 'ventas').strip()
    if dimension not in DIMENSIONS:
        raise ValueError('La dimensión solicitada no está autorizada.')
    if metric not in METRICS and metric != 'formula':
        raise ValueError('La métrica solicitada no está autorizada.')
    metrics = plan.get('metrics') or [metric]
    if not isinstance(metrics, list) or not (1 <= len(metrics) <= 8) or len(metrics) != len(set(metrics)):
        raise ValueError('Se requieren entre 1 y 8 métricas distintas.')
    if metric not in metrics or any(m not in METRICS and m != 'formula' for m in metrics):
        raise ValueError('El conjunto de métricas contiene una columna no permitida.')
    if dimension == 'proveedor_compra' and any(m != 'compras' for m in metrics):
        raise ValueError('Para un proveedor de compra solo existen importes de compras; la utilidad pertenece a la cartera del proveedor de ficha, no puede atribuirse al último comprador.')
    if dimension == 'mes' and any(m in ('stock_unidades', 'stock_valor') for m in metrics):
        raise ValueError('No existe stock histórico mensual para graficar existencias por mes.')
    if dimension == 'proveedor_compra' and any(plan.get(k) for k in ('proveedor', 'formato', 'marca', 'categoria')):
        # product attributes are supported, supplier is matched on actual buy supplier.
        pass
    months = dataset.get('months') or []
    if not months:
        raise ValueError('No hay meses en la importación.')
    start = str(plan.get('desde') or default_start or months[max(0, len(months)-12)])
    end = str(plan.get('hasta') or default_end or months[-1])
    if start not in months or end not in months or months.index(start) > months.index(end):
        raise ValueError('El período solicitado no está disponible en los datos importados.')
    start_i, end_i = months.index(start), months.index(end)
    if metric in ('margen', 'precio_promedio') or metric == 'formula':
        pass
    top_n = min(50, max(1, int(plan.get('top_n') or 15)))
    descending = str(plan.get('orden') or 'desc') != 'asc'
    filters = {key: str(plan.get(key) or '').strip()[:120] for key in
               ('categoria', 'marca', 'formato', 'proveedor', 'sku')}
    groups = collections.defaultdict(lambda: collections.defaultdict(float))
    selected = []
    for i, p in enumerate(dataset['products']):
        category = dataset['categories'][p[2]]
        brand = dataset['brands'][p[3]]
        supplier = dataset['providers'][p[4]]
        fmt = product_format(p)
        if not (_matches(category, filters['categoria']) and _matches(brand, filters['marca'])
                and _matches(fmt, filters['formato']) and _matches(p[0] + ' ' + p[1], filters['sku'])):
            continue
        if dimension != 'proveedor_compra' and not _matches(supplier, filters['proveedor']):
            continue
        selected.append(i)
        if dimension == 'sku': key = p[0] + ' · ' + p[1][:100]
        elif dimension == 'categoria': key = category
        elif dimension == 'marca': key = brand
        elif dimension == 'formato': key = fmt
        elif dimension == 'proveedor_ficha': key = supplier
        elif dimension == 'marca_formato': key = brand + ' / ' + fmt
        elif dimension == 'proveedor_formato': key = supplier + ' / ' + fmt
        else: key = 'TOTAL'
        if dimension not in ('mes', 'proveedor_compra'):
            stock_qty = max(0.0, _number(p[7]))
            groups[key]['stock_unidades'] += stock_qty
            groups[key]['stock_valor'] += stock_qty * max(0.0, _number(p[5]))
    selected_set = set(selected)
    for sku_i, mon_i, qty, revenue, cogs in dataset['sales']:
        if sku_i not in selected_set or not start_i <= mon_i <= end_i:
            continue
        if dimension == 'proveedor_compra':
            continue
        key = months[mon_i] if dimension == 'mes' else _dimension_key(dataset, sku_i, dimension)
        groups[key]['cantidad_vendida'] += _number(qty)
        groups[key]['ventas'] += _number(revenue)
        groups[key]['costo_ventas'] += _number(cogs)
        groups[key]['utilidad'] += _number(revenue) - _number(cogs)
    if dimension == 'proveedor_compra':
        for sku_i, mon_i, suppl_i, amt in dataset.get('supplierPurchases', []):
            if sku_i in selected_set and start_i <= mon_i <= end_i:
                name = dataset['purchaseSuppliers'][suppl_i]
                if _matches(name, filters['proveedor']):
                    groups[name]['compras'] += _number(amt)
    else:
        for sku_i, mon_i, qty, amt in dataset['purchases']:
            if sku_i in selected_set and start_i <= mon_i <= end_i:
                key = months[mon_i] if dimension == 'mes' else _dimension_key(dataset, sku_i, dimension)
                groups[key]['cantidad_comprada'] += _number(qty)
                groups[key]['compras'] += _number(amt)
    expression = str(plan.get('formula') or '').strip()
    if 'formula' in metrics and not expression:
        raise ValueError('Falta la expresión del indicador personalizado.')
    def grouped_measures(values):
        vals = _metrics(values)
        if 'formula' in metrics:
            vals['formula'] = _formula(expression, {key: vals[key] for key in BASE_FIELDS})
        return vals

    result = []
    for label, values in groups.items():
        vals = grouped_measures(values)
        value = vals[metric]
        if value is not None:
            selected_values = {m: round(vals[m], 4) if vals[m] is not None else None for m in metrics}
            result.append({'grupo': label, 'valor': round(value, 4),
                           'metricas': selected_values,
                           'ventas': round(vals['ventas'], 2),
                           'utilidad': round(vals['utilidad'], 2),
                           'compras': round(vals['compras'], 2),
                           'margen': round(vals['margen'], 2) if vals['margen'] is not None else None,
                           'stock_valor': round(vals['stock_valor'], 2)})
    result.sort(key=lambda row: row['valor'], reverse=descending)
    totals = collections.defaultdict(float)
    for value in groups.values():
        for key, val in value.items():
            totals[key] += val
    total_metrics = grouped_measures(totals)
    result_total = total_metrics[metric]
    selected_totals = {m: round(total_metrics[m], 4) if total_metrics[m] is not None else None for m in metrics}
    notes = ['Stock corresponde al corte actual, no al período de ventas. Se valoriza con costo de catálogo.',
             'Cantidades no deben sumarse entre productos con diferentes unidades de medida.']
    if dimension == 'proveedor_compra':
        notes.append('Las compras se atribuyen al proveedor de cada movimiento. No se conocen la utilidad ni las ventas por proveedor de suministro.')
    elif dimension in ('proveedor_ficha', 'proveedor_formato'):
        notes.append('Ventas, utilidad y compras se agrupan por proveedor declarado en ficha del producto, no por trazabilidad de abastecimiento.')
    if filters['proveedor'] and dimension == 'proveedor_compra':
        notes.append('El filtro de proveedor se aplica al proveedor real de la compra.')
    if 'formula' in metrics:
        notes.append('Indicador personalizado calculado con fórmula aritmética validada: ' + expression)
    metric_labels = {m: METRICS.get(m, 'Indicador personalizado: ' + expression) for m in metrics}
    return {'dimension': dimension, 'metrica': metric, 'metricas': metrics,
            'etiquetas': metric_labels, 'totales': selected_totals,
            'etiqueta': METRICS.get(metric, 'Indicador personalizado: ' + expression),
            'periodo': {'desde': start, 'hasta': end}, 'filtros': filters, 'filas': result[:top_n],
            'total': round(result_total, 4) if result_total is not None else None,
            'grupos_evaluados': len(result), 'sku_evaluados': len(selected), 'observaciones': notes}


def _dimension_key(dataset, index, dimension):
    p = dataset['products'][index]
    if dimension == 'sku': return p[0] + ' · ' + p[1][:100]
    if dimension == 'categoria': return dataset['categories'][p[2]]
    if dimension == 'marca': return dataset['brands'][p[3]]
    if dimension == 'formato': return product_format(p)
    if dimension == 'proveedor_ficha': return dataset['providers'][p[4]]
    if dimension == 'marca_formato': return dataset['brands'][p[3]] + ' / ' + product_format(p)
    if dimension == 'categoria_formato': return dataset['categories'][p[2]] + ' / ' + product_format(p)
    if dimension == 'categoria_marca': return dataset['categories'][p[2]] + ' / ' + dataset['brands'][p[3]]
    if dimension == 'categoria_marca_formato': return dataset['categories'][p[2]] + ' / ' + dataset['brands'][p[3]] + ' / ' + product_format(p)
    if dimension == 'proveedor_formato': return dataset['providers'][p[4]] + ' / ' + product_format(p)
    return 'TOTAL'
