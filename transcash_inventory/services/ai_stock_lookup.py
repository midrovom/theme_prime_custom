# -*- coding: utf-8 -*-
"""Safe, deterministic inventory listing queries (no OpenAI request).

Read exclusively the product facts already populated in Odoo, scoped to the
selected company and import snapshot. No SQL or column names from the user.
"""
import re
from .ai_catalog_filters import _norm, _canonical, catalog_values

STOCK_FILTER = re.compile(
    r'(?:stock|existencias?|inventario\s+(?:actual|disponible))\s*'
    r'(?:de\s*)?'
    r'(?:es\s*)?'
    r'(?P<cmp>menor(?:es)?\s+(?:a|de|que)|inferior(?:es)?\s+a|'
    r'menos\s+de|por\s+debajo\s+de|debajo\s+de|<\s*=?|'
    r'mayor(?:es)?\s+(?:a|de|que)|superior(?:es)?\s+a|'
    r'm[aá]s\s+de|por\s+encima\s+de|>\s*=?|igual(?:es)?\s+a|=)\s*'
    r'(?P<num>\d+(?:[.,]\d+)?)', re.IGNORECASE)
FORMAT_IN_TEXT = re.compile(r'(?<!\d)(\d{1,3}(?:[.,]\d{1,2})?)\s*[x×*]\s*'
                            r'(\d{1,3}(?:[.,]\d{1,2})?)(?!\d)', re.IGNORECASE)


def canonical_format(value):
    """Convert 60X1.20 / 60*120 / 60×120 into 60x120 (cm)."""
    match = FORMAT_IN_TEXT.search(str(value or ''))
    if not match:
        return _norm(value).replace(' ', '')
    result = []
    for raw in match.groups():
        number = float(raw.replace(',', '.'))
        # Tile measurements are in cm; 1.20 m means 120 cm, unlike 1.20cm.
        if 0 < number < 3 and ('.' in raw or ',' in raw):
            number *= 100
        result.append('%g' % number)
    return 'x'.join(result)


def detect_stock_lookup(question):
    """Only list SKUs for an unambiguous physical-stock comparison."""
    normalized = _norm(question)
    if not (re.search(r'\b(cuales|que|lista|listado|muestrame|dame|productos|articulos|skus)\b',
                      normalized) or normalized.startswith('stock')):
        return None
    match = STOCK_FILTER.search(normalized)
    if not match:
        return None
    comparator = match.group('cmp').strip()
    op = '>' if any(word in comparator for word in ('mayor', 'superior', 'mas', 'encima', '>')) else '=' if ('igual' in comparator or comparator == '=') else '<'
    if comparator.startswith('<=') or comparator.startswith('>='):
        op = comparator[:2]
    value = float(match.group('num').replace(',', '.'))
    if not 0 <= value <= 100000000:
        return None
    fmt = FORMAT_IN_TEXT.search(question)
    return {'operator': op, 'limit_value': value,
            'formato': fmt.group(0) if fmt else ''}


def _question_catalog_value(question, choices, field):
    """Match product attributes as whole tokens, never by substring category."""
    haystack = _norm(question)
    matches = []
    for choice in choices:
        label = _norm(choice)
        if not label or len(label) < 4 or label.startswith('sin '):
            continue
        suffix = r'(?:s|es)?' if field == 'categoria' else ''
        if re.search(r'(?<!\w)' + re.escape(label) + suffix + r'(?!\w)', haystack):
            matches.append(choice)
    if not matches:
        return ''
    matches.sort(key=lambda candidate: len(_norm(candidate)), reverse=True)
    best = matches[0]
    if any(_norm(item) not in _norm(best) and _norm(best) not in _norm(item)
           for item in matches[1:]):
        raise ValueError('Seleccione un solo valor de %s.' % field)
    return best


def resolve_stock_filters(env, snapshot, question, ui, detected):
    result = {}
    for field in ('categoria', 'marca', 'proveedor'):
        choices = catalog_values(env, snapshot, field)
        supplied = str((ui or {}).get(field) or '').strip()
        mentioned = _question_catalog_value(question, choices, field)
        if supplied and mentioned and _canonical(supplied, choices, field) != _canonical(mentioned, choices, field):
            raise ValueError('La pregunta y el filtro de %s seleccionado son diferentes. Corrija el filtro antes de consultar.' % field)
        result[field] = _canonical(supplied or mentioned, choices, field) if (supplied or mentioned) else ''
    choices = catalog_values(env, snapshot, 'formato')
    selected_ui = str((ui or {}).get('formato') or '').strip()
    mentioned_format = str(detected.get('formato') or '').strip()
    if selected_ui and mentioned_format and canonical_format(selected_ui) != canonical_format(mentioned_format):
        raise ValueError('El formato seleccionado es diferente al solicitado. Corrija el filtro de formato.')
    selected = selected_ui or mentioned_format
    if selected:
        same = [v for v in choices if canonical_format(v) == canonical_format(selected)]
        if not same:
            raise ValueError('No existe el formato solicitado en el catálogo: %s.' % selected[:70])
        result['formato'] = sorted(same)[0]
        result['format_aliases'] = sorted(same)
    else:
        result['formato'] = ''
        result['format_aliases'] = []
    return result


def execute_stock_lookup(env, snapshot, question, ui, detected, period, max_rows=1000):
    filters = resolve_stock_filters(env, snapshot, question, ui, detected)
    operator = detected['operator']
    if operator not in ('<','<=','=','>','>='):
        raise ValueError('Comparación de stock no válida.')
    conditions = ['fp.snapshot_id = %s', 'fp.company_id = %s',
                  'fp.stock_unidades ' + operator + ' %s']
    params = [snapshot.id, snapshot.company_id.id, float(detected['limit_value'])]
    for field, column in (('categoria', 'categoria'), ('marca', 'marca'), ('proveedor', 'proveedor_ficha')):
        if filters[field]:
            conditions.append('LOWER(TRIM(fp.' + column + ')) = LOWER(TRIM(%s))')
            params.append(filters[field])
    if filters['format_aliases']:
        conditions.append('fp.formato = ANY(%s)')
        params.append(filters['format_aliases'])
    where = ' AND '.join(conditions)
    table = 'transcash_inventory_fact_product'
    sql = ('SELECT fp.sku, fp.name, fp.categoria, fp.marca, fp.formato, '
           'fp.proveedor_ficha, fp.stock_unidades, fp.stock_valor '
           'FROM ' + table + ' fp WHERE ' + where +
           ' ORDER BY fp.stock_unidades ASC, fp.sku ASC LIMIT %s')
    env.cr.execute(sql, params + [max_rows])
    records = env.cr.fetchall()
    env.cr.execute('SELECT COUNT(*), COALESCE(SUM(fp.stock_unidades),0), COALESCE(SUM(fp.stock_valor),0) FROM ' + table + ' fp WHERE ' + where, params)
    count, total_units, total_value = env.cr.fetchone()
    metric_keys = ['descripcion', 'categoria', 'marca', 'formato', 'proveedor_ficha', 'stock_unidades', 'stock_valor']
    labels = {'descripcion': 'Descripción', 'categoria': 'Categoría', 'marca': 'Marca',
              'formato': 'Formato', 'proveedor_ficha': 'Proveedor',
              'stock_unidades': 'Stock · cantidad', 'stock_valor': 'Stock · valor USD'}
    rows = []
    for sku, name, cat, brand, fmt, provider, stock, value in records:
        detail = dict(zip(metric_keys, [name or '', cat or '', brand or '', fmt or '',
                                      provider or '', round(float(stock or 0), 4),
                                      round(float(value or 0), 2)]))
        rows.append({'grupo': sku, 'valor': detail['stock_unidades'], 'metricas': detail})
    return {
        'tipo_resultado': 'listado_stock', 'dimension': 'sku',
        'metrica': 'stock_unidades', 'metricas': metric_keys, 'etiquetas': labels,
        # No sum of unit quantities in the UI: catalog may mix m2 / pieces / boxes.
        'totales': {'stock_unidades': None, 'stock_valor': round(float(total_value), 2)},
        'total': int(count), 'grupos_evaluados': int(count), 'sku_evaluados': int(count),
        'filas': rows, 'total_filas': int(count), 'filas_mostradas': len(rows),
        'periodo': {'desde': period[0], 'hasta': period[1]},
        'filtros': {k: v for k, v in filters.items() if k != 'format_aliases'},
        'sql_consulta': sql, 'sql_parametros': params + [max_rows],
    }


def _dataset_filters(dataset, question, ui, detected):
    """Resolve filters against the stored Odoo snapshot when SQL facts aren't built."""
    from .ai_catalog_filters import _canonical
    from .ai_analytics import product_format
    result = {}
    choices_map = {
        'categoria': dataset.get('categories') or [],
        'marca': dataset.get('brands') or [],
        'proveedor': dataset.get('providers') or [],
    }
    for field, choices in choices_map.items():
        supplied = str((ui or {}).get(field) or '').strip()
        mentioned = _question_catalog_value(question, choices, field)
        if supplied and mentioned and _canonical(supplied, choices, field) != _canonical(mentioned, choices, field):
            raise ValueError('La pregunta y el filtro de %s seleccionado son diferentes.' % field)
        result[field] = _canonical(supplied or mentioned, choices, field) if supplied or mentioned else ''
    formats = sorted({product_format(p) for p in dataset.get('products') or []})
    supplied = str((ui or {}).get('formato') or '').strip()
    mentioned = str(detected.get('formato') or '').strip()
    if supplied and mentioned and canonical_format(supplied) != canonical_format(mentioned):
        raise ValueError('El formato seleccionado es diferente al solicitado. Corrija el filtro de formato.')
    chosen = supplied or mentioned
    if chosen:
        result['format_aliases'] = [fmt for fmt in formats if canonical_format(fmt) == canonical_format(chosen)]
        if not result['format_aliases']:
            raise ValueError('No existe el formato solicitado en el catálogo: %s.' % chosen[:70])
        result['formato'] = result['format_aliases'][0]
    else:
        result['format_aliases'] = []
        result['formato'] = ''
    return result


def execute_stock_lookup_snapshot(snapshot, question, ui, detected, period, max_rows=1000):
    """Fast DB-resident snapshot fallback; never materializes or calls OpenAI.

    Old imports are already persisted as a compact JSON attachment in Odoo.
    Reading that attachment is preferable to forcing migration of 100k+ fact
    rows during a simple stock query. New/API imports use the SQL facts path.
    """
    import json
    from .ai_analytics import product_format
    dataset = json.loads(snapshot.get_dashboard_json())
    products = dataset.get('products') or []
    filters = _dataset_filters(dataset, question, ui, detected)
    op = detected['operator']
    if op not in ('<', '<=', '=', '>', '>='):
        raise ValueError('Comparación de stock no válida.')
    threshold = float(detected['limit_value'])
    comparison = {
        '<': lambda value: value < threshold,
        '<=': lambda value: value <= threshold,
        '=': lambda value: value == threshold,
        '>': lambda value: value > threshold,
        '>=': lambda value: value >= threshold,
    }[op]
    labels = {
        'categoria': dataset.get('categories') or [],
        'marca': dataset.get('brands') or [],
        'proveedor': dataset.get('providers') or [],
    }
    filtered = []
    total_value = 0.0
    for p in products:
        if len(p) < 8:
            continue
        category = labels['categoria'][p[2]]
        brand = labels['marca'][p[3]]
        provider = labels['proveedor'][p[4]]
        fmt = product_format(p)
        stock = float(p[7] or 0)
        if not comparison(stock):
            continue
        if (filters['categoria'] and _norm(category) != _norm(filters['categoria']) or
            filters['marca'] and _norm(brand) != _norm(filters['marca']) or
            filters['proveedor'] and _norm(provider) != _norm(filters['proveedor']) or
            filters['format_aliases'] and fmt not in filters['format_aliases']):
            continue
        value = stock * max(0.0, float(p[5] or 0))
        total_value += value
        filtered.append((str(p[0]), str(p[1]), category, brand, fmt, provider, stock, value))
    filtered.sort(key=lambda row: (row[6], row[0]))
    metrics = ['descripcion', 'categoria', 'marca', 'formato', 'proveedor_ficha', 'stock_unidades', 'stock_valor']
    column_names = {'descripcion': 'Descripción', 'categoria': 'Categoría', 'marca': 'Marca',
                    'formato': 'Formato', 'proveedor_ficha': 'Proveedor',
                    'stock_unidades': 'Stock · cantidad', 'stock_valor': 'Stock · valor USD'}
    result_rows = []
    for sku, name, cat, brand, fmt, prov, stock, value in filtered[:max_rows]:
        fields = dict(zip(metrics, [name, cat, brand, fmt, prov, round(stock, 4), round(value, 2)]))
        result_rows.append({'grupo': sku, 'valor': fields['stock_unidades'], 'metricas': fields})
    return {
        'tipo_resultado': 'listado_stock', 'dimension': 'sku',
        'metrica': 'stock_unidades', 'metricas': metrics, 'etiquetas': column_names,
        'totales': {'stock_unidades': None, 'stock_valor': round(total_value, 2)},
        'total': len(filtered), 'grupos_evaluados': len(filtered), 'sku_evaluados': len(filtered),
        'filas': result_rows, 'total_filas': len(filtered), 'filas_mostradas': len(result_rows),
        'periodo': {'desde': period[0], 'hasta': period[1]},
        'filtros': {k: v for k, v in filters.items() if k != 'format_aliases'},
        'sql_consulta': '', 'sql_parametros': [],
    }
